"""Shared Ollama and embedding pipeline configuration.

Settings here are consumed by both the FastAPI application layer
(habittracker/) and the CLI scripts (scripts/embed/).

All values are read from environment variables so no code changes
are needed to reconfigure — just export a different env var.

Environment variables:
    OLLAMA_BASE_URL          — Ollama server URL (default: http://localhost:11434)
    OLLAMA_EMBED_MODEL       — Model for embeddings (default: nomic-embed-text)
    OLLAMA_TIMEOUT_SEC       — HTTP timeout in seconds (default: 60)
    OLLAMA_MAX_RETRIES       — Retry count on transient failures (default: 3)
    OLLAMA_RETRY_BACKOFF_SEC — Initial backoff in seconds; doubles each retry (default: 1)
    EMBED_BATCH_SIZE         — Notes per commit batch in the pipeline (default: 50)
    EMBED_EXPECTED_DIMS      — Expected vector dimensions; mismatches are rejected (default: 768)
"""

import os

# ── Ollama ────────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_TIMEOUT_SEC: float = float(os.getenv("OLLAMA_TIMEOUT_SEC", "60"))
OLLAMA_MAX_RETRIES: int = int(os.getenv("OLLAMA_MAX_RETRIES", "3"))
OLLAMA_RETRY_BACKOFF_SEC: float = float(os.getenv("OLLAMA_RETRY_BACKOFF_SEC", "1"))

# ── Pipeline ──────────────────────────────────────────────────────────────────
EMBED_BATCH_SIZE: int = int(os.getenv("EMBED_BATCH_SIZE", "50"))
EMBED_EXPECTED_DIMS: int = int(os.getenv("EMBED_EXPECTED_DIMS", "768"))
