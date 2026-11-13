from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.submission import Submission
from app.models.user import User
from app.schemas.submission import (
    SubmissionCreateRequest,
    SubmissionListResponse,
    SubmissionResponse,
    SubmissionRunResponse,
)
from app.services.submissions.service import (
    ContestRegistrationError,
    ContestWindowError,
    RateLimitExceeded,
    SubmissionNotFoundError,
    SubmissionService,
)

router = APIRouter(prefix="/submissions", tags=["Submissions"])


def is_staff_user(user: User) -> bool:
    if not hasattr(user, "user_roles"):
        return False
    roles = [ur.role.name for ur in (user.user_roles or []) if ur.role]
    return any(r in ("ADMIN", "SUPERADMIN", "ORGANIZER") for r in roles)


def build_submission_response(
    submission: Submission,
    current_user: Optional[User] = None,
) -> SubmissionResponse:
    is_staff = current_user and is_staff_user(current_user)
    is_owner = current_user and current_user.id == submission.user_id

    # Confidentiality: Only owner or staff can see source code and compile error details
    source_code = submission.source_code if (is_staff or is_owner) else None
    compile_output = submission.compile_output if (is_staff or is_owner) else None

    runs = []
    for r in (submission.runs or []):
        is_sample = r.test_case.is_sample if r.test_case else False
        runs.append(
            SubmissionRunResponse(
                id=r.id,
                test_case_id=r.test_case_id,
                order_num=r.test_case.order_num if r.test_case else None,
                verdict=r.verdict,
                execution_time_ms=r.execution_time_ms,
                execution_memory_kb=r.execution_memory_kb,
                is_sample=is_sample,
            )
        )

    return SubmissionResponse(
        id=submission.id,
        contest_id=submission.contest_id,
        problem_id=submission.problem_id,
        problem_code=submission.problem.code if submission.problem else None,
        problem_title=submission.problem_version.title if submission.problem_version else None,
        user_id=submission.user_id,
        user_username=submission.user.username if submission.user else None,
        language_id=submission.language_id,
        language_name=submission.language.name if submission.language else None,
        source_code=source_code,
        verdict=submission.verdict,
        execution_time_ms=submission.execution_time_ms,
        execution_memory_kb=submission.execution_memory_kb,
        failed_test_case_num=submission.failed_test_case_num,
        compile_output=compile_output,
        submitted_at=submission.submitted_at,
        judged_at=submission.judged_at,
        runs=runs,
    )


@router.post("", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
async def create_submission(
    req: SubmissionCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client_ip = request.client.host if request.client else None
    try:
        submission = await SubmissionService.create_submission(
            db=db,
            user_id=current_user.id,
            problem_id=req.problem_id,
            language_id=req.language_id,
            source_code=req.source_code,
            contest_id=req.contest_id,
            client_ip=client_ip,
        )
        return build_submission_response(submission, current_user)
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )
    except ContestWindowError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ContestRegistrationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=SubmissionListResponse)
async def list_submissions(
    contest_id: Optional[uuid.UUID] = Query(None),
    problem_id: Optional[uuid.UUID] = Query(None),
    user_id: Optional[uuid.UUID] = Query(None),
    verdict: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Authorization: Regular participants only view their own submissions
    target_user_id = user_id
    if not is_staff_user(current_user):
        target_user_id = current_user.id

    submissions, total = await SubmissionService.list_submissions(
        db=db,
        user_id=target_user_id,
        contest_id=contest_id,
        problem_id=problem_id,
        verdict=verdict,
        limit=limit,
        offset=offset,
    )
    items = [build_submission_response(sub, current_user) for sub in submissions]
    return SubmissionListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{id}", response_model=SubmissionResponse)
async def get_submission(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        sub = await SubmissionService.get_submission(db, id)
    except SubmissionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    # Only owner or staff can view submission details
    if sub.user_id != current_user.id and not is_staff_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this submission",
        )

    return build_submission_response(sub, current_user)
