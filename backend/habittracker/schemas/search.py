"""Search schemas.

These are the only types exposed to API consumers for semantic search.
Embedding vectors are never included in any response schema.
"""

import uuid
from dataclasses import dataclass

from pydantic import BaseModel, Field


class NoteSearchHit(BaseModel):
    """A single note returned by semantic search."""

    id: uuid.UUID
    # Content is truncated to a readable snippet — full text is on the notes endpoint.
    snippet: str = Field(description="First 300 chars of the note content.")
    score: float = Field(description="Cosine similarity score (0–1, higher = more similar).")

    model_config = {"from_attributes": True}


class SearchResponse(BaseModel):
    """Response envelope for GET /api/v1/search."""

    query: str
    total: int
    results: list[NoteSearchHit]
