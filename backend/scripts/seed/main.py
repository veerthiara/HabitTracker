"""Seed orchestrator — run with:

    poetry run python -m scripts.seed.main

Or from the repo root:

    make db-seed

The script is fully idempotent: all rows carry fixed UUIDs and are inserted
with ON CONFLICT DO NOTHING, so running it multiple times is safe.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Load DATABASE_URL from infra/local/.env (three dirs up: seed/ → scripts/ → backend/ → repo)
_dotenv_path = Path(__file__).resolve().parents[3] / "infra" / "local" / ".env"
load_dotenv(dotenv_path=_dotenv_path, override=False)

_database_url = os.environ.get("DATABASE_URL")
if not _database_url:
    print("ERROR: DATABASE_URL is not set. Copy infra/local/.env.example → infra/local/.env and fill it in.", file=sys.stderr)
    sys.exit(1)

# Import seeders after env is loaded (they import ORM models).
from scripts.seed import users, habits, bottle_events, notes  # noqa: E402


def run() -> None:
    engine = create_engine(_database_url)
    print("Seeding database …")
    with Session(engine) as session:
        users.seed(session)
        habits.seed(session)
        bottle_events.seed(session)
        notes.seed(session)
        session.commit()
    print("Done. All seed data committed.")


if __name__ == "__main__":
    run()
