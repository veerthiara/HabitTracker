import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from habittracker.models.orm.habittracker.bottle_event import BottleEvent
from habittracker.models.orm.habittracker.habit import Habit
from habittracker.models.orm.habittracker.habit_log import HabitLog
from habittracker.models.orm.habittracker.note import Note
from habittracker.schemas.dashboard import DashboardSummary, HabitSummary
from habittracker.schemas.habit import HabitRead
from habittracker.schemas.note import NoteRead


def get_summary(session: Session, user_id: uuid.UUID, for_date: date) -> DashboardSummary:
    # Active habits.
    habits = list(
        session.scalars(
            select(Habit)
            .where(Habit.user_id == user_id, Habit.is_active.is_(True))
            .order_by(Habit.created_at)
        )
    )

    # Habit IDs logged today.
    start = datetime(for_date.year, for_date.month, for_date.day, tzinfo=timezone.utc)
    end = datetime(for_date.year, for_date.month, for_date.day, 23, 59, 59, tzinfo=timezone.utc)

    logged_today_ids: set[uuid.UUID] = set(
        session.scalars(
            select(HabitLog.habit_id).where(
                HabitLog.user_id == user_id,
                HabitLog.logged_date == for_date,
            )
        )
    )

    # Hydration total today.
    hydration_ml: int = session.scalar(
        select(func.coalesce(func.sum(BottleEvent.volume_ml), 0)).where(
            BottleEvent.user_id == user_id,
            BottleEvent.event_ts >= start,
            BottleEvent.event_ts <= end,
        )
    ) or 0

    # Last 3 notes.
    recent_notes = list(
        session.scalars(
            select(Note)
            .where(Note.user_id == user_id)
            .order_by(Note.created_at.desc())
            .limit(3)
        )
    )

    return DashboardSummary(
        habits_total=len(habits),
        habits_done_today=len(logged_today_ids),
        hydration_today_ml=hydration_ml,
        habit_summaries=[
            HabitSummary(
                habit=HabitRead.model_validate(h),
                done_today=h.id in logged_today_ids,
            )
            for h in habits
        ],
        recent_notes=[NoteRead.model_validate(n) for n in recent_notes],
    )
