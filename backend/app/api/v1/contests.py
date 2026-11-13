from datetime import datetime, timezone
from typing import List, Optional, Union
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_roles
from app.models.user import User
from app.schemas.contest import (
    AddContestProblemRequest,
    ContestCreateRequest,
    ContestDetailResponse,
    ContestProblemResponse,
    ContestRegistrationResponse,
    ContestResponse,
    ContestUpdateRequest,
    ServerTimeResponse,
)
from app.services.contests.service import ContestService

router = APIRouter(prefix="/contests", tags=["Contests"])


@router.get("/time", response_model=ServerTimeResponse)
async def get_server_time():
    """Retrieve authoritative server UTC time for clock synchronization.

    Invariant: Frontend clocks are untrusted. Contest timers must strictly sync against this endpoint.
    """
    now = datetime.now(timezone.utc)
    return ServerTimeResponse(
        server_time=now,
        timestamp=now.timestamp(),
    )


@router.post("", response_model=ContestResponse, status_code=status.HTTP_201_CREATED)
async def create_contest(
    request: ContestCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("ORGANIZER", "ADMIN")),
):
    """Create a new contest (Organizer/Admin only)."""
    try:
        contest = await ContestService.create_contest(
            db=db,
            organizer_id=current_user.id,
            title=request.title,
            slug=request.slug,
            description=request.description,
            start_time=request.start_time,
            end_time=request.end_time,
            freeze_time=request.freeze_time,
            unfreeze_time=request.unfreeze_time,
            rules_type=request.rules_type,
            visibility=request.visibility,
            penalty_per_attempt=request.penalty_per_attempt,
            status=request.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return ContestResponse.model_validate(contest)


@router.get("", response_model=List[ContestResponse])
async def list_contests(
    visibility: Optional[str] = "PUBLIC",
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List contests with authoritative dynamic status."""
    contests = await ContestService.list_contests(
        db=db,
        visibility=visibility,
        status=status_filter,
        skip=skip,
        limit=limit,
    )
    return [ContestResponse.model_validate(c) for c in contests]


@router.get("/{id_or_slug}", response_model=ContestDetailResponse)
async def get_contest(
    id_or_slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Get contest details, registered status, and assigned problems."""
    contest = await ContestService.get_contest(db=db, id_or_slug=id_or_slug)
    if not contest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found")

    is_registered = False
    is_staff = False
    if current_user:
        user_roles = [ur.role.name for ur in current_user.user_roles if ur.role]
        is_staff = "ADMIN" in user_roles or contest.organizer_id == current_user.id
        is_registered = await ContestService.is_user_registered(db, contest.id, current_user.id)

    # Format problems (only if allowed to view)
    problems_resp = []
    if ContestService.can_view_problems(contest, is_organizer_or_admin=is_staff):
        for cp in contest.contest_problems:
            curr_v = next((v for v in cp.problem.versions if v.id == cp.problem.current_version_id), None)
            prob_title = curr_v.title if curr_v else cp.problem.code
            problems_resp.append(
                ContestProblemResponse(
                    id=cp.id,
                    contest_id=cp.contest_id,
                    problem_id=cp.problem_id,
                    problem_code=cp.problem.code,
                    title=prob_title,
                    order_letter=cp.order_letter,
                    points=cp.points,
                    color_code=cp.color_code,
                )
            )

    return ContestDetailResponse(
        id=contest.id,
        title=contest.title,
        slug=contest.slug,
        description=contest.description,
        organizer_id=contest.organizer_id,
        start_time=contest.start_time,
        end_time=contest.end_time,
        freeze_time=contest.freeze_time,
        unfreeze_time=contest.unfreeze_time,
        status=contest.status,
        rules_type=contest.rules_type,
        visibility=contest.visibility,
        penalty_per_attempt=contest.penalty_per_attempt,
        created_at=contest.created_at,
        updated_at=contest.updated_at,
        problems=problems_resp,
        is_registered=is_registered,
    )


@router.post("/{contest_id}/register", response_model=ContestRegistrationResponse)
async def register_contest(
    contest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Register the authenticated user for a contest."""
    try:
        reg = await ContestService.register_participant(
            db=db,
            contest_id=contest_id,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return ContestRegistrationResponse.model_validate(reg)


@router.post("/{contest_id}/problems", response_model=ContestProblemResponse, status_code=status.HTTP_201_CREATED)
async def add_problem_to_contest(
    contest_id: uuid.UUID,
    request: AddContestProblemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("ORGANIZER", "ADMIN")),
):
    """Assign a problem to a contest with an order letter (A, B, C...) (Organizer/Admin only)."""
    contest = await ContestService.get_contest(db=db, id_or_slug=contest_id, sync_status=False)
    if not contest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found")

    user_roles = [ur.role.name for ur in current_user.user_roles if ur.role]
    if contest.organizer_id != current_user.id and "ADMIN" not in user_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only contest organizer or admin can modify contest problems")

    try:
        link = await ContestService.add_problem_to_contest(
            db=db,
            contest_id=contest_id,
            problem_id=request.problem_id,
            order_letter=request.order_letter,
            points=request.points,
            color_code=request.color_code,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Reload with problem details
    updated_contest = await ContestService.get_contest(db=db, id_or_slug=contest_id, sync_status=False)
    cp = next((item for item in updated_contest.contest_problems if item.id == link.id), link)
    curr_v = next((v for v in cp.problem.versions if v.id == cp.problem.current_version_id), None)
    prob_title = curr_v.title if curr_v else cp.problem.code

    return ContestProblemResponse(
        id=cp.id,
        contest_id=cp.contest_id,
        problem_id=cp.problem_id,
        problem_code=cp.problem.code,
        title=prob_title,
        order_letter=cp.order_letter,
        points=cp.points,
        color_code=cp.color_code,
    )


@router.get("/{contest_id}/problems", response_model=List[ContestProblemResponse])
async def get_contest_problems(
    contest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Retrieve the problems assigned to a contest.

    Confidentiality Invariant: Before start_time, problems are confidential and access is rejected with 403 Forbidden.
    """
    contest = await ContestService.get_contest(db=db, id_or_slug=contest_id)
    if not contest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found")

    user_roles = [ur.role.name for ur in current_user.user_roles if ur.role] if current_user else []
    is_staff = "ADMIN" in user_roles or (current_user and contest.organizer_id == current_user.id)

    if not ContestService.can_view_problems(contest, is_organizer_or_admin=is_staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Contest problems are confidential until the contest begins.",
        )

    res = []
    for cp in contest.contest_problems:
        curr_v = next((v for v in cp.problem.versions if v.id == cp.problem.current_version_id), None)
        prob_title = curr_v.title if curr_v else cp.problem.code
        res.append(
            ContestProblemResponse(
                id=cp.id,
                contest_id=cp.contest_id,
                problem_id=cp.problem_id,
                problem_code=cp.problem.code,
                title=prob_title,
                order_letter=cp.order_letter,
                points=cp.points,
                color_code=cp.color_code,
            )
        )
    return res
