from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str
    role: str
    created_at: datetime


class UpdateProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
