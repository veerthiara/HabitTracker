"""Database engine and session factory for the embedding pipeline.

Centralises SQLAlchemy setup so no other module needs to call
create_engine or sessionmaker directly.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from scripts.embed.config import DATABASE_URL

_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
_SessionFactory = sessionmaker(bind=_engine)


def get_session() -> Session:
    """Return a new SQLAlchemy Session.  Caller owns the lifecycle."""
    return _SessionFactory()
