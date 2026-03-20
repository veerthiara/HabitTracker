import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from habittracker.models.orm.habittracker.bottle_event import BottleEvent
from habittracker.schemas.bottle_event import BottleEventCreate


def get_events(
    session: Session,
    user_id: uuid.UUID,
    for_date: date | None = None,
) -> list[BottleEvent]:
    stmt = select(BottleEvent).where(BottleEvent.user_id == user_id)
    if for_date is not None:
        # Filter by UTC calendar day of event_ts.
        start = datetime(for_date.year, for_date.month, for_date.day, tzinfo=timezone.utc)
        end = datetime(for_date.year, for_date.month, for_date.day, 23, 59, 59, tzinfo=timezone.utc)
        stmt = stmt.where(BottleEvent.event_ts >= start, BottleEvent.event_ts <= end)
    return list(session.scalars(stmt.order_by(BottleEvent.event_ts.desc())))


def create_event(session: Session, user_id: uuid.UUID, data: BottleEventCreate) -> BottleEvent:
    event = BottleEvent(user_id=user_id, **data.model_dump())
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def get_event(session: Session, event_id: uuid.UUID, user_id: uuid.UUID) -> BottleEvent | None:
    return session.scalar(
        select(BottleEvent).where(BottleEvent.id == event_id, BottleEvent.user_id == user_id)
    )


def delete_event(session: Session, event: BottleEvent) -> None:
    session.delete(event)
    session.commit()
