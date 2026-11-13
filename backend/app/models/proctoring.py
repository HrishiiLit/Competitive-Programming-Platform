import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProctoringSession(Base):
    __tablename__ = "proctoring_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contest_id = Column(UUID(as_uuid=True), ForeignKey("contests.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="ACTIVE", index=True)
    started_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    suspicion_index = Column(Integer, nullable=False, default=0, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    contest = relationship("Contest")
    user = relationship("User")
    events = relationship("ProctoringEvent", back_populates="session", cascade="all, delete-orphan", order_by="ProctoringEvent.occurred_at")
    evidence = relationship("ProctoringEvidence", back_populates="session", cascade="all, delete-orphan", order_by="ProctoringEvidence.uploaded_at")


class ProctoringEvent(Base):
    __tablename__ = "proctoring_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("proctoring_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default="LOW", index=True)
    metadata_payload = Column(JSONB, nullable=False, default=dict)
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    session = relationship("ProctoringSession", back_populates="events")


class ProctoringEvidence(Base):
    __tablename__ = "proctoring_evidence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("proctoring_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_type = Column(String(30), nullable=False)
    s3_key = Column(Text, nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    face_count = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    session = relationship("ProctoringSession", back_populates="evidence")


class DisciplinaryAction(Base):
    __tablename__ = "disciplinary_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contest_id = Column(UUID(as_uuid=True), ForeignKey("contests.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(30), nullable=False)
    penalty_points = Column(Integer, nullable=False, default=0)
    reason = Column(Text, nullable=False)
    issued_by_proctor_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    issued_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    contest = relationship("Contest")
    user = relationship("User", foreign_keys=[user_id])
    issued_by = relationship("User", foreign_keys=[issued_by_proctor_id])


class ContestAppeal(Base):
    __tablename__ = "contest_appeals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    disciplinary_action_id = Column(UUID(as_uuid=True), ForeignKey("disciplinary_actions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    justification = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="PENDING", index=True)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_notes = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    disciplinary_action = relationship("DisciplinaryAction")
    user = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])
