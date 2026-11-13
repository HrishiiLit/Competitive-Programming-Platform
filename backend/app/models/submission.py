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
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contest_id = Column(UUID(as_uuid=True), ForeignKey("contests.id", ondelete="SET NULL"), nullable=True, index=True)
    problem_id = Column(UUID(as_uuid=True), ForeignKey("problems.id", ondelete="RESTRICT"), nullable=False, index=True)
    problem_version_id = Column(UUID(as_uuid=True), ForeignKey("problem_versions.id", ondelete="RESTRICT"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    language_id = Column(UUID(as_uuid=True), ForeignKey("languages.id", ondelete="RESTRICT"), nullable=False, index=True)
    source_code = Column(Text, nullable=False)
    verdict = Column(String(20), nullable=False, default="PENDING", index=True)
    execution_time_ms = Column(Integer, nullable=True)
    execution_memory_kb = Column(Integer, nullable=True)
    failed_test_case_num = Column(Integer, nullable=True)
    compile_output = Column(Text, nullable=True)
    client_ip = Column(String(45), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    judged_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
    contest = relationship("Contest")
    problem = relationship("Problem")
    problem_version = relationship("ProblemVersion")
    language = relationship("Language")
    runs = relationship("SubmissionRun", back_populates="submission", cascade="all, delete-orphan", order_by="SubmissionRun.created_at")


class SubmissionRun(Base):
    __tablename__ = "submission_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True)
    test_case_id = Column(UUID(as_uuid=True), ForeignKey("test_cases.id", ondelete="RESTRICT"), nullable=False, index=True)
    verdict = Column(String(20), nullable=False)
    execution_time_ms = Column(Integer, nullable=False, default=0)
    execution_memory_kb = Column(Integer, nullable=False, default=0)
    judge0_token = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    submission = relationship("Submission", back_populates="runs")
    test_case = relationship("TestCase")


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False, index=True)
    aggregate_type = Column(String(50), nullable=False)
    aggregate_id = Column(String(64), nullable=False, index=True)
    payload = Column(JSONB, nullable=False, default=dict)
    status = Column(String(20), nullable=False, default="PENDING", index=True)
    retry_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    published_at = Column(DateTime(timezone=True), nullable=True)


class Judge0Callback(Base):
    __tablename__ = "judge0_callbacks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    judge0_token = Column(String(64), nullable=False, index=True)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True)
    status_id = Column(Integer, nullable=False)
    payload = Column(JSONB, nullable=False, default=dict)
    processed = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
