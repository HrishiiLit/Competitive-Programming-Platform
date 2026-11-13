import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Contest(Base):
    __tablename__ = "contests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(200), nullable=False)
    slug = Column(String(220), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=False, default="")
    organizer_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False, index=True)
    freeze_time = Column(DateTime(timezone=True), nullable=True)
    unfreeze_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=False, default="DRAFT", index=True)
    rules_type = Column(String(20), nullable=False, default="ICPC")
    visibility = Column(String(20), nullable=False, default="PUBLIC")
    penalty_per_attempt = Column(Integer, nullable=False, default=20)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    organizer = relationship("User", foreign_keys=[organizer_id], lazy="selectin")
    contest_problems = relationship("ContestProblem", back_populates="contest", cascade="all, delete-orphan", order_by="ContestProblem.order_letter", lazy="selectin")
    registrations = relationship("ContestRegistration", back_populates="contest", cascade="all, delete-orphan", lazy="selectin")


class ContestProblem(Base):
    __tablename__ = "contest_problems"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contest_id = Column(UUID(as_uuid=True), ForeignKey("contests.id", ondelete="CASCADE"), nullable=False, index=True)
    problem_id = Column(UUID(as_uuid=True), ForeignKey("problems.id", ondelete="RESTRICT"), nullable=False, index=True)
    order_letter = Column(String(5), nullable=False)
    points = Column(Integer, nullable=False, default=1)
    color_code = Column(String(7), nullable=False, default="#3B82F6")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("contest_id", "order_letter", name="uq_contest_problem_order"),
        UniqueConstraint("contest_id", "problem_id", name="uq_contest_problem_link"),
    )

    contest = relationship("Contest", back_populates="contest_problems")
    problem = relationship("Problem", lazy="selectin")


class ContestRegistration(Base):
    __tablename__ = "contest_registrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contest_id = Column(UUID(as_uuid=True), ForeignKey("contests.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False, default="PARTICIPANT")
    registered_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    approved = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("contest_id", "user_id", name="uq_contest_user_registration"),
    )

    contest = relationship("Contest", back_populates="registrations")
    user = relationship("User")
