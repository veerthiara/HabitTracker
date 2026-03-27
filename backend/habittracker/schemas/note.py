import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NoteCreate(BaseModel):
    content: str = Field(..., min_length=1)
    source: str = Field("manual", pattern="^(manual|ai)$")


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    content: str
    source: str
    created_at: datetime
    updated_at: datetime
