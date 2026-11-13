from datetime import datetime
from typing import List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class SubmissionCreateRequest(BaseModel):
    problem_id: uuid.UUID
    language_id: uuid.UUID
    source_code: str = Field(..., min_length=1, max_length=256000)
    contest_id: Optional[uuid.UUID] = None


class SubmissionRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    test_case_id: uuid.UUID
    order_num: Optional[int] = None
    verdict: str
    execution_time_ms: int
    execution_memory_kb: int
    is_sample: Optional[bool] = None


class SubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contest_id: Optional[uuid.UUID] = None
    problem_id: uuid.UUID
    problem_code: Optional[str] = None
    problem_title: Optional[str] = None
    user_id: uuid.UUID
    user_username: Optional[str] = None
    language_id: uuid.UUID
    language_name: Optional[str] = None
    source_code: Optional[str] = None
    verdict: str
    execution_time_ms: Optional[int] = None
    execution_memory_kb: Optional[int] = None
    failed_test_case_num: Optional[int] = None
    compile_output: Optional[str] = None
    submitted_at: datetime
    judged_at: Optional[datetime] = None
    runs: List[SubmissionRunResponse] = Field(default_factory=list)


class SubmissionListResponse(BaseModel):
    items: List[SubmissionResponse]
    total: int
    limit: int
    offset: int
