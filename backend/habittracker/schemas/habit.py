import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HabitCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    frequency: str = Field("daily", pattern="^(daily|weekly|custom)$")


class HabitUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    frequency: str | None = Field(None, pattern="^(daily|weekly|custom)$")
    is_active: bool | None = None


class HabitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    frequency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
