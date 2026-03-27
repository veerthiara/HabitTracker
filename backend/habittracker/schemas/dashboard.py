from pydantic import BaseModel

from habittracker.schemas.habit import HabitRead
from habittracker.schemas.note import NoteRead


class HabitSummary(BaseModel):
    habit: HabitRead
    done_today: bool


class DashboardSummary(BaseModel):
    habits_total: int
    habits_done_today: int
    hydration_today_ml: int
    habit_summaries: list[HabitSummary]
    recent_notes: list[NoteRead]
