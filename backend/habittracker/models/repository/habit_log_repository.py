import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from habittracker.models.orm.habittracker.habit_log import HabitLog
from habittracker.schemas.habit_log import HabitLogCreate


def get_logs(
    session: Session,
    user_id: uuid.UUID,
    habit_id: uuid.UUID | None = None,
    logged_date: date | None = None,
) -> list[HabitLog]:
    stmt = select(HabitLog).where(HabitLog.user_id == user_id)
    if habit_id is not None:
        stmt = stmt.where(HabitLog.habit_id == habit_id)
    if logged_date is not None:
        stmt = stmt.where(HabitLog.logged_date == logged_date)
    stmt = stmt.order_by(HabitLog.logged_date.desc())
    return list(session.scalars(stmt))


def log_exists(session: Session, habit_id: uuid.UUID, user_id: uuid.UUID, logged_date: date) -> bool:
    return session.scalar(
        select(HabitLog).where(
            HabitLog.habit_id == habit_id,
            HabitLog.user_id == user_id,
            HabitLog.logged_date == logged_date,
        )
    ) is not None


def create_log(session: Session, user_id: uuid.UUID, data: HabitLogCreate) -> HabitLog:
    log = HabitLog(user_id=user_id, **data.model_dump())
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


def get_log(session: Session, log_id: uuid.UUID, user_id: uuid.UUID) -> HabitLog | None:
    return session.scalar(
        select(HabitLog).where(HabitLog.id == log_id, HabitLog.user_id == user_id)
    )


def delete_log(session: Session, log: HabitLog) -> None:
    session.delete(log)
    session.commit()
