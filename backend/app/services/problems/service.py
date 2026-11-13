from datetime import datetime, timezone
from typing import List, Optional
import uuid
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.contest import Contest, ContestProblem
from app.models.problem import Problem, ProblemVersion, TestCase


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProblemService:
    @staticmethod
    async def create_problem(
        db: AsyncSession,
        author_id: uuid.UUID,
        code: str,
        title: str,
        statement_markdown: str,
        time_limit_ms: int = 1000,
        memory_limit_mb: int = 256,
        input_format: str = "",
        output_format: str = "",
        notes: Optional[str] = None,
        checker_type: str = "token",
        checker_code: Optional[str] = None,
    ) -> Problem:
        # Check code uniqueness
        stmt = select(Problem).where(Problem.code == code)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise ValueError(f"Problem code '{code}' already exists")

        now = utc_now()
        problem_id = uuid.uuid4()
        version_id = uuid.uuid4()

        problem = Problem(
            id=problem_id,
            code=code,
            author_id=author_id,
            current_version_id=version_id,
            created_at=now,
            updated_at=now,
        )
        db.add(problem)

        version = ProblemVersion(
            id=version_id,
            problem_id=problem_id,
            version_number=1,
            title=title,
            statement_markdown=statement_markdown,
            time_limit_ms=time_limit_ms,
            memory_limit_mb=memory_limit_mb,
            input_format=input_format,
            output_format=output_format,
            notes=notes,
            checker_type=checker_type,
            checker_code=checker_code,
            is_published=False,
            created_at=now,
        )
        db.add(version)

        await db.commit()

        # Reload with selectinload
        return await ProblemService.get_problem(db, problem_id)

    @staticmethod
    async def get_problem(db: AsyncSession, problem_id: uuid.UUID) -> Optional[Problem]:
        stmt = (
            select(Problem)
            .options(
                selectinload(Problem.versions).selectinload(ProblemVersion.test_cases),
                selectinload(Problem.author),
            )
            .where(Problem.id == problem_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_problem_by_code(db: AsyncSession, code: str) -> Optional[Problem]:
        stmt = (
            select(Problem)
            .options(
                selectinload(Problem.versions).selectinload(ProblemVersion.test_cases),
                selectinload(Problem.author),
            )
            .where(Problem.code == code)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_problems(
        db: AsyncSession,
        author_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Problem]:
        stmt = (
            select(Problem)
            .options(
                selectinload(Problem.versions).selectinload(ProblemVersion.test_cases),
                selectinload(Problem.author),
            )
            .order_by(desc(Problem.created_at))
            .offset(skip)
            .limit(limit)
        )
        if author_id:
            stmt = stmt.where(Problem.author_id == author_id)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def is_version_locked(db: AsyncSession, version_id: uuid.UUID) -> bool:
        """A problem version is immutable if its problem is bound to an active or past contest."""
        stmt = (
            select(ProblemVersion)
            .where(ProblemVersion.id == version_id)
        )
        version = (await db.execute(stmt)).scalar_one_or_none()
        if not version:
            raise ValueError("Problem version not found")

        # Check if the problem is in any contest that is ACTIVE, FROZEN, COMPLETED, or FINALIZED
        contest_stmt = (
            select(Contest)
            .join(ContestProblem, ContestProblem.contest_id == Contest.id)
            .where(
                ContestProblem.problem_id == version.problem_id,
                Contest.status.in_(["ACTIVE", "FROZEN", "COMPLETED", "FINALIZED"]),
            )
        )
        res = await db.execute(contest_stmt)
        active_contest = res.scalar_one_or_none()
        return active_contest is not None

    @staticmethod
    async def assert_version_mutable(db: AsyncSession, version_id: uuid.UUID) -> None:
        if await ProblemService.is_version_locked(db, version_id):
            raise ValueError("Problem version is immutable because it is attached to an active or past contest")

    @staticmethod
    async def create_new_version(
        db: AsyncSession,
        problem_id: uuid.UUID,
        title: str,
        statement_markdown: str,
        time_limit_ms: int = 1000,
        memory_limit_mb: int = 256,
        input_format: str = "",
        output_format: str = "",
        notes: Optional[str] = None,
        checker_type: str = "token",
        checker_code: Optional[str] = None,
        copy_test_cases_from_version_id: Optional[uuid.UUID] = None,
    ) -> ProblemVersion:
        problem = await ProblemService.get_problem(db, problem_id)
        if not problem:
            raise ValueError("Problem not found")

        # Get latest version number
        num_stmt = select(func.max(ProblemVersion.version_number)).where(ProblemVersion.problem_id == problem_id)
        max_num = (await db.execute(num_stmt)).scalar() or 0
        new_version_num = max_num + 1

        now = utc_now()
        new_version_id = uuid.uuid4()

        new_version = ProblemVersion(
            id=new_version_id,
            problem_id=problem_id,
            version_number=new_version_num,
            title=title,
            statement_markdown=statement_markdown,
            time_limit_ms=time_limit_ms,
            memory_limit_mb=memory_limit_mb,
            input_format=input_format,
            output_format=output_format,
            notes=notes,
            checker_type=checker_type,
            checker_code=checker_code,
            is_published=False,
            created_at=now,
        )
        db.add(new_version)

        # Copy testcases if requested
        if copy_test_cases_from_version_id:
            old_tests = await ProblemService.get_test_cases(db, copy_test_cases_from_version_id, include_hidden=True)
            for ot in old_tests:
                copied_test = TestCase(
                    id=uuid.uuid4(),
                    problem_version_id=new_version_id,
                    order_num=ot.order_num,
                    input_data=ot.input_data,
                    expected_output=ot.expected_output,
                    s3_input_key=ot.s3_input_key,
                    s3_output_key=ot.s3_output_key,
                    is_sample=ot.is_sample,
                    explanation=ot.explanation,
                    points=ot.points,
                    created_at=now,
                )
                db.add(copied_test)

        problem.current_version_id = new_version_id
        problem.updated_at = now

        await db.commit()

        # Reload version with testcases
        v_stmt = (
            select(ProblemVersion)
            .options(selectinload(ProblemVersion.test_cases))
            .where(ProblemVersion.id == new_version_id)
        )
        return (await db.execute(v_stmt)).scalar_one()

    @staticmethod
    async def add_test_case(
        db: AsyncSession,
        version_id: uuid.UUID,
        input_data: Optional[str] = None,
        expected_output: Optional[str] = None,
        is_sample: bool = False,
        explanation: Optional[str] = None,
        points: int = 0,
        s3_input_key: Optional[str] = None,
        s3_output_key: Optional[str] = None,
    ) -> TestCase:
        # Check immutability
        await ProblemService.assert_version_mutable(db, version_id)

        # Get next order num
        order_stmt = select(func.max(TestCase.order_num)).where(TestCase.problem_version_id == version_id)
        max_order = (await db.execute(order_stmt)).scalar() or 0

        test_case = TestCase(
            id=uuid.uuid4(),
            problem_version_id=version_id,
            order_num=max_order + 1,
            input_data=input_data,
            expected_output=expected_output,
            is_sample=is_sample,
            explanation=explanation,
            points=points,
            s3_input_key=s3_input_key,
            s3_output_key=s3_output_key,
            created_at=utc_now(),
        )
        db.add(test_case)
        await db.commit()
        await db.refresh(test_case)
        return test_case

    @staticmethod
    async def get_test_cases(
        db: AsyncSession,
        version_id: uuid.UUID,
        include_hidden: bool = False,
    ) -> List[TestCase]:
        """Fetch test cases for a problem version.

        Crucial invariant (Mandatory Constraint 2):
        Never expose hidden test cases to participant-facing queries.
        """
        stmt = (
            select(TestCase)
            .where(TestCase.problem_version_id == version_id)
            .order_by(TestCase.order_num)
        )
        if not include_hidden:
            stmt = stmt.where(TestCase.is_sample == True)

        result = await db.execute(stmt)
        return list(result.scalars().all())
