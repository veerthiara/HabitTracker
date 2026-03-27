"""Seed demo bottle / hydration events."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from habittracker.models.orm.habittracker.bottle_event import BottleEvent
from scripts.seed.users import DEMO_USER_ID

_BASE_ID  = uuid.UUID("00000000-0000-0000-0000-000000002000")
_BASE_TS  = datetime.now(tz=timezone.utc).replace(hour=8, minute=0, second=0, microsecond=0)

# Three events today, spread across the morning.
ROWS = [
    {
        "id": uuid.UUID(int=_BASE_ID.int + 1),
        "user_id": DEMO_USER_ID,
        "event_ts": _BASE_TS,
        "volume_ml": 500,
        "notes": "After morning run",
    },
    {
        "id": uuid.UUID(int=_BASE_ID.int + 2),
        "user_id": DEMO_USER_ID,
        "event_ts": _BASE_TS + timedelta(hours=2),
        "volume_ml": 330,
        "notes": None,
    },
    {
        "id": uuid.UUID(int=_BASE_ID.int + 3),
        "user_id": DEMO_USER_ID,
        "event_ts": _BASE_TS + timedelta(hours=4),
        "volume_ml": 500,
        "notes": "Mid-morning",
    },
]


def seed(session: Session) -> None:
    for row in ROWS:
        stmt = (
            insert(BottleEvent)
            .values(**row)
            .on_conflict_do_nothing(index_elements=["id"])
        )
        session.execute(stmt)
    session.flush()
    print(f"  [bottle_events] seeded {len(ROWS)} row(s)")
