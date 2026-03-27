"""Semantic search API endpoint.

GET /api/v1/search?q=<query>&limit=<1-20>

Embeds the query using the configured Ollama provider, then queries the
notes table using pgvector cosine-distance. Returns ranked note snippets.

Design decisions:
- Embedding happens inline on the request path (acceptable for local/dev use).
  For production, a dedicated embedding service or caching layer would be added.
- Vectors are never returned to the caller — only id, snippet, and score.
- Notes without an embedding are silently excluded (run `make embed-notes` first).
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from habittracker.api.deps import get_current_user_id
from habittracker.models.repository.search_repository import search_notes
from habittracker.models.repository.session import get_session
from habittracker.schemas.search import NoteSearchHit, SearchResponse
from habittracker.providers.base import EmbeddingError
from habittracker.providers.ollama import OllamaProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

# Single shared provider instance — reuses the same httpx.Client across requests.
_provider = OllamaProvider()

_SNIPPET_LEN = 300


@router.get("/", response_model=SearchResponse)
def semantic_search(
    q: Annotated[str, Query(min_length=1, max_length=500, description="Search query text")],
    limit: Annotated[int, Query(ge=1, le=20, description="Max results to return")] = 5,
    session: Session = Depends(get_session),
    user_id=Depends(get_current_user_id),
) -> SearchResponse:
    """Search notes semantically using pgvector cosine similarity.

    Notes that have not been embedded yet are excluded from results.
    Run `make embed-notes` to embed any unprocessed notes before searching.
    """
    # 1. Embed the query using Ollama.
    try:
        query_vector = _provider.embed(q)
    except EmbeddingError as exc:
        logger.error("Failed to embed search query: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Embedding service unavailable. Ensure Ollama is running.",
        ) from exc

    # 2. Query the DB for the closest notes.
    rows = search_notes(session, user_id, query_vector, limit=limit)

    # 3. Build response — truncate to snippet, never return raw vectors.
    hits = [
        NoteSearchHit(
            id=row.id,
            snippet=row.content[:_SNIPPET_LEN],
            score=round(row.score, 4),
        )
        for row in rows
    ]

    return SearchResponse(query=q, total=len(hits), results=hits)
