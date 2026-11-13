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


class Problem(Base):
    __tablename__ = "problems"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), nullable=False, unique=True, index=True)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    current_version_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    author = relationship("User", foreign_keys=[author_id], lazy="selectin")
    versions = relationship("ProblemVersion", back_populates="problem", cascade="all, delete-orphan", order_by="desc(ProblemVersion.version_number)", lazy="selectin")


class ProblemVersion(Base):
    __tablename__ = "problem_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problem_id = Column(UUID(as_uuid=True), ForeignKey("problems.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    statement_markdown = Column(Text, nullable=False)
    time_limit_ms = Column(Integer, nullable=False, default=1000)
    memory_limit_mb = Column(Integer, nullable=False, default=256)
    input_format = Column(Text, nullable=False, default="")
    output_format = Column(Text, nullable=False, default="")
    notes = Column(Text, nullable=True)
    checker_type = Column(String(30), nullable=False, default="token")
    checker_code = Column(Text, nullable=True)
    is_published = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("problem_id", "version_number", name="uq_problem_version_number"),
    )

    problem = relationship("Problem", back_populates="versions")
    test_cases = relationship("TestCase", back_populates="problem_version", cascade="all, delete-orphan", order_by="TestCase.order_num", lazy="selectin")


class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problem_version_id = Column(UUID(as_uuid=True), ForeignKey("problem_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    order_num = Column(Integer, nullable=False)
    input_data = Column(Text, nullable=True)
    expected_output = Column(Text, nullable=True)
    s3_input_key = Column(Text, nullable=True)
    s3_output_key = Column(Text, nullable=True)
    is_sample = Column(Boolean, nullable=False, default=False)
    explanation = Column(Text, nullable=True)
    points = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("problem_version_id", "order_num", name="uq_problem_test_order"),
    )

    problem_version = relationship("ProblemVersion", back_populates="test_cases")
