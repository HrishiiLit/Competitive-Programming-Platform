import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CodeDraft(Base):
    __tablename__ = "code_drafts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    contest_id = Column(UUID(as_uuid=True), ForeignKey("contests.id", ondelete="CASCADE"), nullable=True, index=True)
    problem_id = Column(UUID(as_uuid=True), ForeignKey("problems.id", ondelete="CASCADE"), nullable=False, index=True)
    language_id = Column(UUID(as_uuid=True), ForeignKey("languages.id", ondelete="RESTRICT"), nullable=False)
    source_code = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        UniqueConstraint("user_id", "contest_id", "problem_id", name="uq_user_contest_problem_draft"),
    )

    user = relationship("User")
    contest = relationship("Contest")
    problem = relationship("Problem")
    language = relationship("Language")


class ContestStanding(Base):
    __tablename__ = "contest_standings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contest_id = Column(UUID(as_uuid=True), ForeignKey("contests.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rank = Column(Integer, nullable=False, default=0)
    problems_solved = Column(Integer, nullable=False, default=0)
    total_penalty_minutes = Column(Integer, nullable=False, default=0)
    is_frozen = Column(Boolean, nullable=False, default=False)
    last_submission_time = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        UniqueConstraint("contest_id", "user_id", name="uq_contest_user_standing"),
    )

    contest = relationship("Contest")
    user = relationship("User")
    problem_results = relationship("StandingProblemResult", back_populates="standing", cascade="all, delete-orphan")


class StandingProblemResult(Base):
    __tablename__ = "standing_problem_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    standing_id = Column(UUID(as_uuid=True), ForeignKey("contest_standings.id", ondelete="CASCADE"), nullable=False, index=True)
    problem_id = Column(UUID(as_uuid=True), ForeignKey("problems.id", ondelete="RESTRICT"), nullable=False, index=True)
    solved = Column(Boolean, nullable=False, default=False)
    attempt_count = Column(Integer, nullable=False, default=0)
    penalty_minutes = Column(Integer, nullable=False, default=0)
    first_solved_time = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        UniqueConstraint("standing_id", "problem_id", name="uq_standing_problem_result"),
    )

    standing = relationship("ContestStanding", back_populates="problem_results")
    problem = relationship("Problem")
