from datetime import datetime
from typing import List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ContestCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    slug: str = Field(..., min_length=3, max_length=220, pattern=r"^[a-z0-9-]+$")
    description: str = ""
    start_time: datetime
    end_time: datetime
    freeze_time: Optional[datetime] = None
    unfreeze_time: Optional[datetime] = None
    rules_type: str = "ICPC"
    visibility: str = "PUBLIC"
    penalty_per_attempt: int = 20
    status: str = "UPCOMING"


class ContestUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    freeze_time: Optional[datetime] = None
    unfreeze_time: Optional[datetime] = None
    visibility: Optional[str] = None
    penalty_per_attempt: Optional[int] = None
    status: Optional[str] = None


class AddContestProblemRequest(BaseModel):
    problem_id: uuid.UUID
    order_letter: str = Field(..., min_length=1, max_length=5, pattern=r"^[A-Z0-9]+$")
    points: int = 1
    color_code: str = Field(default="#3B82F6", pattern=r"^#[0-9a-fA-F]{6}$")


class ContestProblemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contest_id: uuid.UUID
    problem_id: uuid.UUID
    problem_code: str
    title: str
    order_letter: str
    points: int
    color_code: str


class ContestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    description: str
    organizer_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    freeze_time: Optional[datetime] = None
    unfreeze_time: Optional[datetime] = None
    status: str
    rules_type: str
    visibility: str
    penalty_per_attempt: int
    created_at: datetime
    updated_at: datetime


class ContestDetailResponse(ContestResponse):
    problems: List[ContestProblemResponse] = []
    is_registered: bool = False


class ContestRegistrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contest_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    registered_at: datetime
    approved: bool


class ServerTimeResponse(BaseModel):
    server_time: datetime
    timestamp: float
