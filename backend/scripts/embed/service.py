"""Embedding service — orchestrates the pipeline logic.

This module knows about batching, dimension validation, error accounting,
and logging. It does NOT know about Ollama specifics (uses the provider
abstraction) or SQL details (uses repository functions).

This separation makes both the provider and the DB layer independently
testable and swappable.
"""

import logging
import time
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from scripts.embed.config import EMBED_BATCH_SIZE, EMBED_EXPECTED_DIMS
from scripts.embed.providers.base import EmbeddingError, EmbeddingProvider
from scripts.embed.repository import (
    NoteRow,
    fetch_unembedded_notes,
    update_note_embedding,
)

logger = logging.getLogger(__name__)


@dataclass
class EmbedResult:
    processed: int = 0
    skipped: int = 0
    errors: int = 0
    error_ids: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.errors == 0


def _validate_dims(vector: list[float], expected: int, note_id: str) -> bool:
    """Return True if dimensions match, log a warning and return False otherwise."""
    if len(vector) != expected:
        logger.warning(
            "Dimension mismatch for note %s: expected %d, got %d — skipping",
            note_id,
            expected,
            len(vector),
        )
        return False
    return True


def embed_notes(
    session: Session,
    provider: EmbeddingProvider,
    *,
    batch_size: int = EMBED_BATCH_SIZE,
    expected_dims: int = EMBED_EXPECTED_DIMS,
    inter_batch_delay: float = 0.1,
) -> EmbedResult:
    """Embed all notes that currently have no embedding.

    Args:
        session:          SQLAlchemy session (pipeline opens its own commits).
        provider:         Any :class:`EmbeddingProvider` implementation.
        batch_size:       How many notes to commit in one transaction.
        expected_dims:    Reject vectors that don't match this dimension count.
        inter_batch_delay: Seconds to pause between batches (reduces Ollama load).

    Returns:
        An :class:`EmbedResult` with counts of processed/skipped/error rows.
    """
    notes: list[NoteRow] = fetch_unembedded_notes(session)

    if not notes:
        logger.info("No notes need embedding — nothing to do.")
        return EmbedResult()

    logger.info("Found %d note(s) to embed.", len(notes))
    result = EmbedResult()

    for batch_start in range(0, len(notes), batch_size):
        batch = notes[batch_start : batch_start + batch_size]

        for note in batch:
            note_id_str = str(note.id)
            try:
                vector = provider.embed(note.content)

                if not _validate_dims(vector, expected_dims, note_id_str):
                    result.skipped += 1
                    continue

                update_note_embedding(session, note.id, vector)
                result.processed += 1
                logger.info("  ✓ %s (%d dims)", note_id_str, len(vector))

            except EmbeddingError as exc:
                result.errors += 1
                result.error_ids.append(note_id_str)
                logger.error("  ✗ %s — %s", note_id_str, exc)

        session.commit()
        logger.debug("Batch committed (%d notes).", len(batch))

        # Pause between batches to be polite to the local Ollama process.
        if batch_start + batch_size < len(notes):
            time.sleep(inter_batch_delay)

    return result
