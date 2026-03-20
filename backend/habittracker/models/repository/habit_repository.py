import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from habittracker.models.orm.habittracker.habit import Habit
from habittracker.schemas.habit import HabitCreate, HabitUpdate


def get_habits(session: Session, user_id: uuid.UUID) -> list[Habit]:
    return list(
        session.scalars(
            select(Habit)
            .where(Habit.user_id == user_id, Habit.is_active.is_(True))
            .order_by(Habit.created_at)
        )
    )


def get_habit(session: Session, habit_id: uuid.UUID, user_id: uuid.UUID) -> Habit | None:
    return session.scalar(
        select(Habit).where(Habit.id == habit_id, Habit.user_id == user_id)
    )


def create_habit(session: Session, user_id: uuid.UUID, data: HabitCreate) -> Habit:
    habit = Habit(user_id=user_id, **data.model_dump())
    session.add(habit)
    session.commit()
    session.refresh(habit)
    return habit


def update_habit(session: Session, habit: Habit, data: HabitUpdate) -> Habit:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(habit, field, value)
    session.commit()
    session.refresh(habit)
    return habit


def delete_habit(session: Session, habit: Habit) -> None:
    # Soft-delete: mark inactive rather than destroying history.
    habit.is_active = False
    session.commit()
