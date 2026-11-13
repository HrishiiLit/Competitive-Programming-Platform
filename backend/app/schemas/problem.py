from datetime import datetime
from typing import List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class TestCaseCreateRequest(BaseModel):
    input_data: Optional[str] = None
    expected_output: Optional[str] = None
    is_sample: bool = False
    explanation: Optional[str] = None
    points: int = 0
    s3_input_key: Optional[str] = None
    s3_output_key: Optional[str] = None


class TestCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_num: int
    input_data: Optional[str] = None
    expected_output: Optional[str] = None
    is_sample: bool
    explanation: Optional[str] = None
    points: int


class ProblemVersionCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    statement_markdown: str = Field(..., min_length=1)
    time_limit_ms: int = Field(default=1000, ge=250, le=15000)
    memory_limit_mb: int = Field(default=256, ge=16, le=1024)
    input_format: str = ""
    output_format: str = ""
    notes: Optional[str] = None
    checker_type: str = "token"
    checker_code: Optional[str] = None
    copy_test_cases_from_version_id: Optional[uuid.UUID] = None


class ProblemVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    problem_id: uuid.UUID
    version_number: int
    title: str
    statement_markdown: str
    time_limit_ms: int
    memory_limit_mb: int
    input_format: str
    output_format: str
    notes: Optional[str] = None
    checker_type: str
    is_published: bool
    test_cases: List[TestCaseResponse] = []
    created_at: datetime


class ProblemCreateRequest(BaseModel):
    code: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Z0-9_-]+$")
    title: str = Field(..., min_length=1, max_length=200)
    statement_markdown: str = Field(..., min_length=1)
    time_limit_ms: int = Field(default=1000, ge=250, le=15000)
    memory_limit_mb: int = Field(default=256, ge=16, le=1024)
    input_format: str = ""
    output_format: str = ""
    notes: Optional[str] = None
    checker_type: str = "token"
    checker_code: Optional[str] = None


class ProblemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    author_id: uuid.UUID
    current_version_id: Optional[uuid.UUID] = None
    current_version: Optional[ProblemVersionResponse] = None
    created_at: datetime
    updated_at: datetime
