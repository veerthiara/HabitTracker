"""Embedding pipeline entry point.

Usage:
    make embed-notes
    # or directly:
    cd backend && poetry run python -m scripts.embed.main

Idempotent: only notes where embedding IS NULL are processed.
Safe to re-run at any time.

All configuration is in scripts/embed/config.py (driven by env vars).
All SQL is in scripts/embed/repository.py.
All provider logic is in scripts/embed/providers/.
All pipeline logic is in scripts/embed/service.py.
"""

import logging
import sys

from scripts.embed.db import get_session
from scripts.embed.providers.ollama import OllamaProvider
from scripts.embed.service import embed_notes

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

