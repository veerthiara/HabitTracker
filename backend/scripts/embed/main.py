"""Embedding pipeline entry point.

Usage:
    make embed-notes
    # or directly:
    cd backend && poetry run python -m scripts.embed.main

Idempotent: only notes where embedding IS NULL are processed.
Safe to re-run at any time.

Package layout:
    scripts/embed/db.py                                  — .env + DATABASE_URL + session
    habittracker/core/config.py                          — Ollama/pipeline settings
    habittracker/providers/ollama.py                     — embedding provider
    habittracker/services/embedding_service.py           — pipeline logic
    habittracker/models/repository/embedding_repository.py — SQL
"""

import logging
import sys

from scripts.embed.db import get_session
from habittracker.providers.ollama import OllamaProvider
from habittracker.services.embedding_service import embed_notes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def run() -> None:
    provider = OllamaProvider()

    with get_session() as session:
        result = embed_notes(session, provider)

    logger.info(
        "Done. processed=%d  skipped=%d  errors=%d",
        result.processed,
        result.skipped,
        result.errors,
    )

    if not result.success:
        logger.error("Failed note IDs: %s", result.error_ids)
        sys.exit(1)


if __name__ == "__main__":
    run()

