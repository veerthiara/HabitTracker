"""Database engine and session factory for the embedding pipeline.

This is the only scripts-layer module that is not in habittracker/.
It owns .env loading and DATABASE_URL — infrastructure concerns that
belong to the CLI runner, not the application layer.

Environment variables:
    DATABASE_URL — Postgres connection string (required).
                   Set in infra/local/.env or backend/.env.

All other settings (Ollama, batch sizes, etc.) live in
habittracker/core/config.py and are read from env vars there.
"""

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Search relative to this file so both `make embed-notes` (cwd=repo root)
# and direct `poetry run python -m scripts.embed.main` invocations work.
_env_candidates = [
    os.path.join(os.path.dirname(__file__), "../../../infra/local/.env"),
    os.path.join(os.path.dirname(__file__), "../../.env"),
]
for _path in _env_candidates:
    if os.path.exists(_path):
        load_dotenv(dotenv_path=_path)
        break

DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
    sys.exit(1)

_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
_SessionFactory = sessionmaker(bind=_engine)


def get_session() -> Session:
    """Return a new SQLAlchemy Session. Caller owns the lifecycle."""
    return _SessionFactory()
