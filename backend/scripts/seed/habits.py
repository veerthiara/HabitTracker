"""Seed demo habits and habit logs.

All IDs are fixed so repeated runs are idempotent.
"""
import uuid
from datetime import date, timedelta

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from habittracker.models.orm.habittracker.habit import Habit
from habittracker.models.orm.habittracker.habit_log import HabitLog
from scripts.seed.users import DEMO_USER_ID

HABIT_MORNING_RUN_ID = uuid.UUID("00000000-0000-0000-0000-000000000011")
HABIT_READ_ID        = uuid.UUID("00000000-0000-0000-0000-000000000012")
HABIT_MEDITATE_ID    = uuid.UUID("00000000-0000-0000-0000-000000000013")

HABIT_ROWS = [
    {
        "id": HABIT_MORNING_RUN_ID,
        "user_id": DEMO_USER_ID,
        "name": "Morning run",
        "description": "30-minute easy run before breakfast",
        "frequency": "daily",
        "is_active": True,
    },
    {
        "id": HABIT_READ_ID,
        "user_id": DEMO_USER_ID,
        "name": "Read 30 min",
        "description": "Read a book — no screens",
        "frequency": "daily",
        "is_active": True,
    },
    {
        "id": HABIT_MEDITATE_ID,
        "user_id": DEMO_USER_ID,
        "name": "Meditate",
        "description": "10-minute guided meditation",
        "frequency": "daily",
        "is_active": True,
    },
]

# Generate log entries for the past 7 days for the first two habits.
_today = date.today()
_LOG_BASE_ID = uuid.UUID("00000000-0000-0000-0000-000000001000")

def _log_rows() -> list[dict]:
    rows = []
    habit_ids = [HABIT_MORNING_RUN_ID, HABIT_READ_ID]
    for day_offset in range(7):
        for i, habit_id in enumerate(habit_ids):
            # Build a deterministic UUID from the base + a simple offset.
            offset = day_offset * 10 + i + 1
            log_id = uuid.UUID(int=_LOG_BASE_ID.int + offset)
            rows.append(
                {
                    "id": log_id,
                    "habit_id": habit_id,
                    "user_id": DEMO_USER_ID,
                    "logged_date": _today - timedelta(days=day_offset),
                    "notes": None,
                }
            )
    return rows


def seed(session: Session) -> None:
    for row in HABIT_ROWS:
        stmt = insert(Habit).values(**row).on_conflict_do_nothing(index_elements=["id"])
        session.execute(stmt)

    log_rows = _log_rows()
    for row in log_rows:
        stmt = insert(HabitLog).values(**row).on_conflict_do_nothing(index_elements=["id"])
        session.execute(stmt)

    session.flush()
    print(f"  [habits] seeded {len(HABIT_ROWS)} habit(s), {len(log_rows)} log(s)")
