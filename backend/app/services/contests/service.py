from datetime import datetime, timezone
from typing import List, Optional, Tuple, Union
import uuid
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.contest import Contest, ContestProblem, ContestRegistration
from app.models.problem import Problem


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class ContestService:
    @staticmethod
    def calculate_contest_status(contest: Contest, current_time: Optional[datetime] = None) -> str:
        """Evaluate authoritative server-side contest state according to fixed-window timing rules.

        State Flow: DRAFT -> UPCOMING -> ACTIVE -> FROZEN -> COMPLETED -> FINALIZED
        """
        now = ensure_utc(current_time or utc_now())
        start = ensure_utc(contest.start_time)
        end = ensure_utc(contest.end_time)
        freeze = ensure_utc(contest.freeze_time)

        # Persistent administrative states
        if contest.status == "DRAFT":
            return "DRAFT"
        if contest.status == "FINALIZED":
            return "FINALIZED"

        if now < start:
            return "UPCOMING"
        elif freeze and freeze <= now < end:
            return "FROZEN"
        elif start <= now < end:
            return "ACTIVE"
        else:
            return "COMPLETED"

    @staticmethod
    async def create_contest(
        db: AsyncSession,
        organizer_id: uuid.UUID,
        title: str,
        slug: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
        freeze_time: Optional[datetime] = None,
        unfreeze_time: Optional[datetime] = None,
        rules_type: str = "ICPC",
        visibility: str = "PUBLIC",
        penalty_per_attempt: int = 20,
        status: str = "UPCOMING",
    ) -> Contest:
        start_time = ensure_utc(start_time)
        end_time = ensure_utc(end_time)
        freeze_time = ensure_utc(freeze_time)
        unfreeze_time = ensure_utc(unfreeze_time)

        if start_time >= end_time:
            raise ValueError("Contest start_time must be strictly earlier than end_time")

        if freeze_time:
            if not (start_time < freeze_time <= end_time):
                raise ValueError("freeze_time must be between start_time and end_time")

        # Check slug uniqueness
        stmt = select(Contest).where(Contest.slug == slug)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise ValueError(f"Contest slug '{slug}' already taken")

        now = utc_now()
        contest_id = uuid.uuid4()

        contest = Contest(
            id=contest_id,
            title=title,
            slug=slug,
            description=description,
            organizer_id=organizer_id,
            start_time=start_time,
            end_time=end_time,
            freeze_time=freeze_time,
            unfreeze_time=unfreeze_time,
            rules_type=rules_type,
            visibility=visibility,
            penalty_per_attempt=penalty_per_attempt,
            status=status,
            created_at=now,
            updated_at=now,
        )
        db.add(contest)
        await db.commit()

        return await ContestService.get_contest(db, contest_id)

    @staticmethod
    async def get_contest(
        db: AsyncSession,
        id_or_slug: Union[uuid.UUID, str],
        sync_status: bool = True,
    ) -> Optional[Contest]:
        stmt = (
            select(Contest)
            .options(
                selectinload(Contest.organizer),
                selectinload(Contest.contest_problems).selectinload(ContestProblem.problem).selectinload(Problem.versions),
                selectinload(Contest.registrations),
            )
        )
        if isinstance(id_or_slug, uuid.UUID):
            stmt = stmt.where(Contest.id == id_or_slug)
        else:
            try:
                val_uuid = uuid.UUID(id_or_slug)
                stmt = stmt.where(Contest.id == val_uuid)
            except ValueError:
                stmt = stmt.where(Contest.slug == id_or_slug)

        result = await db.execute(stmt)
        contest = result.scalar_one_or_none()

        if contest and sync_status:
            dyn_status = ContestService.calculate_contest_status(contest)
            if dyn_status != contest.status and contest.status not in ["DRAFT", "FINALIZED"]:
                contest.status = dyn_status
                await db.commit()

        return contest

    @staticmethod
    async def list_contests(
        db: AsyncSession,
        visibility: Optional[str] = "PUBLIC",
        status: Optional[str] = None,
        organizer_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Contest]:
        stmt = (
            select(Contest)
            .options(
                selectinload(Contest.organizer),
                selectinload(Contest.contest_problems),
            )
            .order_by(desc(Contest.start_time))
            .offset(skip)
            .limit(limit)
        )
        if visibility:
            stmt = stmt.where(Contest.visibility == visibility)
        if status:
            stmt = stmt.where(Contest.status == status)
        if organizer_id:
            stmt = stmt.where(Contest.organizer_id == organizer_id)

        result = await db.execute(stmt)
        contests = list(result.scalars().all())

        # Sync statuses
        for c in contests:
            dyn_status = ContestService.calculate_contest_status(c)
            if dyn_status != c.status and c.status not in ["DRAFT", "FINALIZED"]:
                c.status = dyn_status

        return contests

    @staticmethod
    async def add_problem_to_contest(
        db: AsyncSession,
        contest_id: uuid.UUID,
        problem_id: uuid.UUID,
        order_letter: str,
        points: int = 1,
        color_code: str = "#3B82F6",
    ) -> ContestProblem:
        contest = await ContestService.get_contest(db, contest_id, sync_status=False)
        if not contest:
            raise ValueError("Contest not found")

        # Problem order letter must be unique in this contest
        for cp in contest.contest_problems:
            if cp.order_letter.upper() == order_letter.upper():
                raise ValueError(f"Order letter '{order_letter}' already assigned in this contest")
            if cp.problem_id == problem_id:
                raise ValueError("Problem already added to this contest")

        # Problem must exist
        p_stmt = select(Problem).where(Problem.id == problem_id)
        problem = (await db.execute(p_stmt)).scalar_one_or_none()
        if not problem:
            raise ValueError("Problem not found")

        link = ContestProblem(
            id=uuid.uuid4(),
            contest_id=contest_id,
            problem_id=problem_id,
            order_letter=order_letter.upper(),
            points=points,
            color_code=color_code,
            created_at=utc_now(),
        )
        db.add(link)
        await db.commit()
        await db.refresh(link)
        return link

    @staticmethod
    async def register_participant(
        db: AsyncSession,
        contest_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str = "PARTICIPANT",
    ) -> ContestRegistration:
        contest = await ContestService.get_contest(db, contest_id)
        if not contest:
            raise ValueError("Contest not found")

        if contest.status in ["COMPLETED", "FINALIZED"]:
            raise ValueError("Registration closed: Contest has already concluded")

        # Check existing registration
        stmt = select(ContestRegistration).where(
            ContestRegistration.contest_id == contest_id,
            ContestRegistration.user_id == user_id,
        )
        reg = (await db.execute(stmt)).scalar_one_or_none()
        if reg:
            return reg  # Idempotent registration

        registration = ContestRegistration(
            id=uuid.uuid4(),
            contest_id=contest_id,
            user_id=user_id,
            role=role,
            approved=True,
            registered_at=utc_now(),
        )
        db.add(registration)
        await db.commit()
        await db.refresh(registration)
        return registration

    @staticmethod
    async def is_user_registered(
        db: AsyncSession,
        contest_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        stmt = select(ContestRegistration).where(
            ContestRegistration.contest_id == contest_id,
            ContestRegistration.user_id == user_id,
            ContestRegistration.approved == True,
        )
        res = (await db.execute(stmt)).scalar_one_or_none()
        return res is not None

    @staticmethod
    def can_view_problems(
        contest: Contest,
        user_id: Optional[uuid.UUID] = None,
        is_organizer_or_admin: bool = False,
    ) -> bool:
        """Enforces mandatory access invariant:

        Problems in upcoming contests are confidential and cannot be viewed
        by participants before the authoritative start time.
        """
        if is_organizer_or_admin:
            return True
        status = ContestService.calculate_contest_status(contest)
        return status in ["ACTIVE", "FROZEN", "COMPLETED", "FINALIZED"]
