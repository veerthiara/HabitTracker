"""Seed demo users.

Uses fixed UUIDs so the script is fully idempotent — safe to run many times.
"""
import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from habittracker.models.orm.habittracker.user import User

# Fixed seed UUID — easy to spot in the DB, never collides with real data.
DEMO_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

ROWS = [
    {"id": DEMO_USER_ID},
]


def seed(session: Session) -> None:
    for row in ROWS:
        stmt = insert(User).values(**row).on_conflict_do_nothing(index_elements=["id"])
        session.execute(stmt)
    session.flush()
    print(f"  [users] seeded {len(ROWS)} row(s)")
