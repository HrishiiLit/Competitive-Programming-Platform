from datetime import datetime, timezone
from typing import List, Optional, Tuple
import uuid
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.contest import Contest, ContestProblem, ContestRegistration
from app.models.problem import Problem, ProblemVersion
from app.models.submission import OutboxEvent, Submission, SubmissionRun
from app.models.user import Language, User
from app.services.contests.service import ContestService


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class RateLimitExceeded(Exception):
    pass


class ContestWindowError(Exception):
    pass


class ContestRegistrationError(Exception):
    pass


class SubmissionNotFoundError(Exception):
    pass


class SubmissionService:
    RATE_LIMIT_SECONDS = 5.0

    @classmethod
    async def create_submission(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        problem_id: uuid.UUID,
        language_id: uuid.UUID,
        source_code: str,
        contest_id: Optional[uuid.UUID] = None,
        client_ip: Optional[str] = None,
    ) -> Submission:
        now = utc_now()

        # 1. Validate problem and get current active version
        stmt = (
            select(Problem)
            .where(Problem.id == problem_id)
            .options(selectinload(Problem.versions))
        )
        problem = (await db.execute(stmt)).scalar_one_or_none()
        if not problem:
            raise ValueError(f"Problem {problem_id} does not exist")

        if not problem.current_version_id:
            # Fall back to latest version if current_version_id is not set
            if not problem.versions:
                raise ValueError("Problem has no versions or test cases available")
            version = problem.versions[0]
        else:
            version_stmt = select(ProblemVersion).where(ProblemVersion.id == problem.current_version_id)
            version = (await db.execute(version_stmt)).scalar_one_or_none()
            if not version:
                raise ValueError("Active problem version not found")

        # 2. Validate language
        lang_stmt = select(Language).where(Language.id == language_id)
        language = (await db.execute(lang_stmt)).scalar_one_or_none()
        if not language or not language.enabled:
            raise ValueError("Requested programming language is not supported or currently disabled")

        # 3. Rate limiting check (max 1 submission every 5 seconds per user per problem)
        latest_sub_stmt = (
            select(Submission.submitted_at)
            .where(Submission.user_id == user_id, Submission.problem_id == problem_id)
            .order_by(desc(Submission.submitted_at))
            .limit(1)
        )
        last_submitted_at = (await db.execute(latest_sub_stmt)).scalar_one_or_none()
        if last_submitted_at:
            last_dt = ensure_utc(last_submitted_at)
            elapsed = (now - last_dt).total_seconds()
            if elapsed < cls.RATE_LIMIT_SECONDS:
                remaining = cls.RATE_LIMIT_SECONDS - elapsed
                raise RateLimitExceeded(
                    f"Submission rate limit exceeded. Please wait {remaining:.1f}s before submitting again to this problem."
                )

        # 4. Contest validation
        if contest_id:
            contest_stmt = select(Contest).where(Contest.id == contest_id)
            contest = (await db.execute(contest_stmt)).scalar_one_or_none()
            if not contest:
                raise ValueError(f"Contest {contest_id} not found")

            # Verify problem is registered to contest
            cp_stmt = select(ContestProblem).where(
                ContestProblem.contest_id == contest_id,
                ContestProblem.problem_id == problem_id,
            )
            cp = (await db.execute(cp_stmt)).scalar_one_or_none()
            if not cp:
                raise ValueError("Problem is not part of this contest")

            # Check contest window status
            status = ContestService.calculate_contest_status(contest, now)
            if status in ("DRAFT", "UPCOMING"):
                raise ContestWindowError("Contest has not started yet. Submissions are rejected.")
            elif status in ("COMPLETED", "FINALIZED"):
                raise ContestWindowError("Contest has concluded. Submissions are closed.")
            elif status not in ("ACTIVE", "FROZEN"):
                raise ContestWindowError(f"Contest is in state '{status}'. Submissions are rejected.")

            # Check user registration
            reg_stmt = select(ContestRegistration).where(
                ContestRegistration.contest_id == contest_id,
                ContestRegistration.user_id == user_id,
                ContestRegistration.approved.is_(True),
            )
            registration = (await db.execute(reg_stmt)).scalar_one_or_none()
            if not registration:
                raise ContestRegistrationError("User is not registered for this contest")

        # 5. Transactional Outbox insertion (Atomic submission and outbox event)
        submission_id = uuid.uuid4()
        submission = Submission(
            id=submission_id,
            contest_id=contest_id,
            problem_id=problem_id,
            problem_version_id=version.id,
            user_id=user_id,
            language_id=language_id,
            source_code=source_code,
            verdict="PENDING",
            client_ip=client_ip,
            submitted_at=now,
        )
        db.add(submission)

        outbox_event = OutboxEvent(
            id=uuid.uuid4(),
            event_type="submission.created",
            aggregate_type="submission",
            aggregate_id=str(submission_id),
            payload={
                "submission_id": str(submission_id),
                "contest_id": str(contest_id) if contest_id else None,
                "problem_id": str(problem_id),
                "problem_version_id": str(version.id),
                "user_id": str(user_id),
                "language_id": str(language_id),
                "judge0_language_id": language.judge0_language_id,
                "time_limit_ms": version.time_limit_ms,
                "memory_limit_mb": version.memory_limit_mb,
            },
            status="PENDING",
            retry_count=0,
            created_at=now,
        )
        db.add(outbox_event)

        await db.commit()
        await db.refresh(submission)
        return submission

    @classmethod
    async def get_submission(
        cls,
        db: AsyncSession,
        submission_id: uuid.UUID,
    ) -> Submission:
        stmt = (
            select(Submission)
            .where(Submission.id == submission_id)
            .options(
                selectinload(Submission.runs),
                selectinload(Submission.problem),
                selectinload(Submission.problem_version),
                selectinload(Submission.language),
                selectinload(Submission.user),
                selectinload(Submission.contest),
            )
        )
        sub = (await db.execute(stmt)).scalar_one_or_none()
        if not sub:
            raise SubmissionNotFoundError(f"Submission {submission_id} not found")
        return sub

    @classmethod
    async def list_submissions(
        cls,
        db: AsyncSession,
        user_id: Optional[uuid.UUID] = None,
        contest_id: Optional[uuid.UUID] = None,
        problem_id: Optional[uuid.UUID] = None,
        verdict: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Submission], int]:
        filters = []
        if user_id:
            filters.append(Submission.user_id == user_id)
        if contest_id:
            filters.append(Submission.contest_id == contest_id)
        if problem_id:
            filters.append(Submission.problem_id == problem_id)
        if verdict:
            filters.append(Submission.verdict == verdict)

        count_stmt = select(func.count(Submission.id))
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(Submission)
            .options(
                selectinload(Submission.runs),
                selectinload(Submission.problem),
                selectinload(Submission.language),
                selectinload(Submission.user),
            )
            .order_by(desc(Submission.submitted_at))
            .limit(limit)
            .offset(offset)
        )
        if filters:
            stmt = stmt.where(*filters)

        results = (await db.execute(stmt)).scalars().all()
        return list(results), total
