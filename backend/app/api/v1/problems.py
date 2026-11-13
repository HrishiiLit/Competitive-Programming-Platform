from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_roles
from app.models.user import User
from app.schemas.problem import (
    ProblemCreateRequest,
    ProblemResponse,
    ProblemVersionCreateRequest,
    ProblemVersionResponse,
    TestCaseCreateRequest,
    TestCaseResponse,
)
from app.services.problems.service import ProblemService

router = APIRouter(prefix="/problems", tags=["Problems"])


def build_problem_response(problem, current_version=None) -> ProblemResponse:
    v_resp = None
    if current_version:
        v_resp = ProblemVersionResponse(
            id=current_version.id,
            problem_id=current_version.problem_id,
            version_number=current_version.version_number,
            title=current_version.title,
            statement_markdown=current_version.statement_markdown,
            time_limit_ms=current_version.time_limit_ms,
            memory_limit_mb=current_version.memory_limit_mb,
            input_format=current_version.input_format,
            output_format=current_version.output_format,
            notes=current_version.notes,
            checker_type=current_version.checker_type,
            is_published=current_version.is_published,
            test_cases=[
                TestCaseResponse(
                    id=tc.id,
                    order_num=tc.order_num,
                    input_data=tc.input_data,
                    expected_output=tc.expected_output,
                    is_sample=tc.is_sample,
                    explanation=tc.explanation,
                    points=tc.points,
                )
                for tc in (current_version.test_cases or [])
                if tc.is_sample  # only public sample tests in default problem payload
            ],
            created_at=current_version.created_at,
        )

    return ProblemResponse(
        id=problem.id,
        code=problem.code,
        author_id=problem.author_id,
        current_version_id=problem.current_version_id,
        current_version=v_resp,
        created_at=problem.created_at,
        updated_at=problem.updated_at,
    )


@router.post("", response_model=ProblemResponse, status_code=status.HTTP_201_CREATED)
async def create_problem(
    request: ProblemCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("ORGANIZER", "ADMIN")),
):
    """Create a new problem along with initial version 1 (Organizer/Admin only)."""
    try:
        problem = await ProblemService.create_problem(
            db=db,
            author_id=current_user.id,
            code=request.code,
            title=request.title,
            statement_markdown=request.statement_markdown,
            time_limit_ms=request.time_limit_ms,
            memory_limit_mb=request.memory_limit_mb,
            input_format=request.input_format,
            output_format=request.output_format,
            notes=request.notes,
            checker_type=request.checker_type,
            checker_code=request.checker_code,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    current_ver = problem.versions[0] if problem.versions else None
    return build_problem_response(problem, current_ver)


@router.get("", response_model=List[ProblemResponse])
async def list_problems(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List problems."""
    problems = await ProblemService.list_problems(db=db, skip=skip, limit=limit)
    res = []
    for p in problems:
        current_ver = next((v for v in p.versions if v.id == p.current_version_id), None)
        if not current_ver and p.versions:
            current_ver = p.versions[0]
        res.append(build_problem_response(p, current_ver))
    return res


@router.get("/{problem_id}", response_model=ProblemResponse)
async def get_problem(
    problem_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get problem details and current version."""
    problem = await ProblemService.get_problem(db=db, problem_id=problem_id)
    if not problem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found")

    current_ver = next((v for v in problem.versions if v.id == problem.current_version_id), None)
    if not current_ver and problem.versions:
        current_ver = problem.versions[0]

    return build_problem_response(problem, current_ver)


@router.post("/{problem_id}/versions", response_model=ProblemVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_problem_version(
    problem_id: uuid.UUID,
    request: ProblemVersionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("ORGANIZER", "ADMIN")),
):
    """Create a new version for a problem."""
    problem = await ProblemService.get_problem(db=db, problem_id=problem_id)
    if not problem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found")

    user_roles = [ur.role.name for ur in current_user.user_roles if ur.role]
    if problem.author_id != current_user.id and "ADMIN" not in user_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only problem author or admin can create new versions")

    try:
        new_version = await ProblemService.create_new_version(
            db=db,
            problem_id=problem_id,
            title=request.title,
            statement_markdown=request.statement_markdown,
            time_limit_ms=request.time_limit_ms,
            memory_limit_mb=request.memory_limit_mb,
            input_format=request.input_format,
            output_format=request.output_format,
            notes=request.notes,
            checker_type=request.checker_type,
            checker_code=request.checker_code,
            copy_test_cases_from_version_id=request.copy_test_cases_from_version_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return ProblemVersionResponse.model_validate(new_version)


@router.post("/{problem_id}/versions/{version_id}/testcases", response_model=TestCaseResponse, status_code=status.HTTP_201_CREATED)
async def add_testcase(
    problem_id: uuid.UUID,
    version_id: uuid.UUID,
    request: TestCaseCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("ORGANIZER", "ADMIN")),
):
    """Add a testcase to a problem version (locked if version is attached to an active/past contest)."""
    try:
        testcase = await ProblemService.add_test_case(
            db=db,
            version_id=version_id,
            input_data=request.input_data,
            expected_output=request.expected_output,
            is_sample=request.is_sample,
            explanation=request.explanation,
            points=request.points,
            s3_input_key=request.s3_input_key,
            s3_output_key=request.s3_output_key,
        )
    except ValueError as e:
        if "immutable" in str(e).lower() or "locked" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return TestCaseResponse.model_validate(testcase)


@router.get("/{problem_id}/versions/{version_id}/testcases", response_model=List[TestCaseResponse])
async def get_testcases(
    problem_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Get test cases for a problem version.

    Confidentiality Invariant: Participants only receive sample test cases.
    """
    user_roles = [ur.role.name for ur in current_user.user_roles if ur.role] if current_user else []
    is_staff = "ADMIN" in user_roles or "ORGANIZER" in user_roles

    test_cases = await ProblemService.get_test_cases(db=db, version_id=version_id, include_hidden=is_staff)
    return [TestCaseResponse.model_validate(tc) for tc in test_cases]
