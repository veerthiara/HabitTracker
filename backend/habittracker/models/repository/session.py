"""SQLAlchemy session factory and FastAPI dependency."""
import os
from collections.abc import Generator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Load from infra/local/.env when running locally; no-op if already in env.
_dotenv_path = Path(__file__).resolve().parents[4] / "infra" / "local" / ".env"
if _dotenv_path.exists():
    load_dotenv(dotenv_path=_dotenv_path, override=False)

_engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a transactional Session per request."""
    with Session(_engine) as session:
        yield session
