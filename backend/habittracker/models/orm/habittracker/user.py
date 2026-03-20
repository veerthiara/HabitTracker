import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from habittracker.models.orm.base import Base

if TYPE_CHECKING:
    from habittracker.models.orm.habittracker.habit import Habit
    from habittracker.models.orm.habittracker.habit_log import HabitLog
    from habittracker.models.orm.habittracker.bottle_event import BottleEvent
    from habittracker.models.orm.habittracker.note import Note
    from habittracker.models.orm.habittracker.daily_summary import DailySummary


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    habits: Mapped[list["Habit"]] = relationship(back_populates="user")
    habit_logs: Mapped[list["HabitLog"]] = relationship(back_populates="user")
    bottle_events: Mapped[list["BottleEvent"]] = relationship(back_populates="user")
    notes: Mapped[list["Note"]] = relationship(back_populates="user")
    daily_summaries: Mapped[list["DailySummary"]] = relationship(back_populates="user")
