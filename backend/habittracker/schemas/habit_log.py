import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class HabitLogCreate(BaseModel):
    habit_id: uuid.UUID
    logged_date: date
    notes: str | None = None


class HabitLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    habit_id: uuid.UUID
    user_id: uuid.UUID
    logged_date: date
    notes: str | None
    created_at: datetime
