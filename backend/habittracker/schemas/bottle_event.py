import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BottleEventCreate(BaseModel):
    event_ts: datetime
    volume_ml: int = Field(..., gt=0, le=5000)
    notes: str | None = None


class BottleEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    event_ts: datetime
    volume_ml: int
    notes: str | None
    created_at: datetime
