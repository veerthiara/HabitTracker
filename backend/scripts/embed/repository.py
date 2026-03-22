"""Embedding repository — all SQL for the embedding pipeline lives here.

Keeps raw SQL out of service/main so the persistence layer is easy to
test and swap independently.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class NoteRow:
    id: uuid.UUID
    content: str


def vector_to_literal(vector: list[float]) -> str:
    """Serialise a float list to the pgvector text literal format '[f1,f2,...]'.

    This format is accepted by ``CAST(:vec AS vector)`` in SQL.
    """
    return "[" + ",".join(repr(v) for v in vector) + "]"


def fetch_unembedded_notes(session: Session) -> list[NoteRow]:
    """Return all notes that have no embedding yet, ordered by creation time."""
    rows = session.execute(
        text(
            "SELECT id, content FROM notes "
            "WHERE embedding IS NULL "
            "ORDER BY created_at"
        )
    ).fetchall()
    return [NoteRow(id=row.id, content=row.content) for row in rows]


def update_note_embedding(
    session: Session, note_id: uuid.UUID, vector: list[float]
) -> None:
    """Persist *vector* for the given note.

    Uses ``CAST(:vec AS vector)`` to avoid SQLAlchemy's ``::`` cast syntax
    conflicting with named-parameter parsing under psycopg2.
    """
    session.execute(
        text(
            "UPDATE notes "
            "SET embedding = CAST(:vec AS vector) "
            "WHERE id = :id"
        ),
        {"vec": vector_to_literal(vector), "id": str(note_id)},
    )
