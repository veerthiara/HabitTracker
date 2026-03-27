"""Search repository — pgvector cosine-similarity queries.

All SQL for semantic search lives here. No embedding vectors are returned
to callers — only business fields (id, content snippet, score).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from habittracker.models.repository.embedding_repository import vector_to_literal


@dataclass(frozen=True)
class NoteSearchRow:
    id: uuid.UUID
    content: str          # full content — snippet truncation done in the API layer
    score: float          # cosine similarity (1 - cosine_distance)


def search_notes(
    session: Session,
    user_id: uuid.UUID,
    query_vector: list[float],
    limit: int = 5,
) -> list[NoteSearchRow]:
    """Return the top-*limit* notes closest to *query_vector* for *user_id*.

    Uses the pgvector ``<=>`` cosine-distance operator.  The score returned
    is ``1 - distance`` so that higher values mean more similar.

    Only notes that have an embedding (embedding IS NOT NULL) are searched.
    Notes belonging to other users are excluded.

    Args:
        session:       SQLAlchemy session (read-only query).
        user_id:       Restrict results to this user's notes.
        query_vector:  Embedding of the search query (must match column dims).
        limit:         Maximum number of results to return (1–20).

    Returns:
        List of :class:`NoteSearchRow` ordered by descending similarity.
    """
    vec_literal = vector_to_literal(query_vector)

    rows = session.execute(
        text(
            "SELECT id, content, "
            "  1 - (embedding <=> CAST(:vec AS vector)) AS score "
            "FROM notes "
            "WHERE user_id = :user_id "
            "  AND embedding IS NOT NULL "
            "ORDER BY embedding <=> CAST(:vec AS vector) "
            "LIMIT :limit"
        ),
        {
            "vec": vec_literal,
            "user_id": str(user_id),
            "limit": limit,
        },
    ).fetchall()

    return [
        NoteSearchRow(id=row.id, content=row.content, score=float(row.score))
        for row in rows
    ]
