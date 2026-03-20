"""Seed demo notes."""
import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from habittracker.models.orm.habittracker.note import Note
from scripts.seed.users import DEMO_USER_ID

_BASE_ID = uuid.UUID("00000000-0000-0000-0000-000000003000")

ROWS = [
    {
        "id": uuid.UUID(int=_BASE_ID.int + 1),
        "user_id": DEMO_USER_ID,
        "content": "Felt great after the morning run today — keep the streak going.",
        "source": "manual",
    },
    {
        "id": uuid.UUID(int=_BASE_ID.int + 2),
        "user_id": DEMO_USER_ID,
        "content": "Meditation session was harder to focus today, mind kept wandering.",
        "source": "manual",
    },
]


def seed(session: Session) -> None:
    for row in ROWS:
        stmt = insert(Note).values(**row).on_conflict_do_nothing(index_elements=["id"])
        session.execute(stmt)
    session.flush()
    print(f"  [notes] seeded {len(ROWS)} row(s)")
