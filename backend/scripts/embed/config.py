"""Embedding pipeline configuration.

All environment variables and tunables live here.
To change a setting, update the env var — no code changes needed in any
other file.

Environment variables (set in backend/.env or infra/local/.env):
    DATABASE_URL          — Postgres connection string (required)
    OLLAMA_BASE_URL       — Ollama server base URL (default: http://localhost:11434)
    OLLAMA_EMBED_MODEL    — model used for embeddings (default: nomic-embed-text)
    OLLAMA_TIMEOUT_SEC    — HTTP timeout for Ollama requests in seconds (default: 60)
    OLLAMA_MAX_RETRIES    — transient failure retry count (default: 3)
    OLLAMA_RETRY_BACKOFF_SEC — initial backoff in seconds, doubles each retry (default: 1)
    EMBED_BATCH_SIZE      — notes per commit batch (default: 50)
    EMBED_EXPECTED_DIMS   — expected vector dimensions, validated before saving (default: 768)
"""

import os
import sys

from dotenv import load_dotenv

# Resolve .env search path relative to the backend/ working directory.
# Supports both `make embed-notes` (cwd=repo root) and direct invocation.
_env_candidates = [
    os.path.join(os.path.dirname(__file__), "../../../infra/local/.env"),
    os.path.join(os.path.dirname(__file__), "../../.env"),
]
for _path in _env_candidates:
    if os.path.exists(_path):
        load_dotenv(dotenv_path=_path)
        break

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
    sys.exit(1)

# ── Ollama ────────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_TIMEOUT_SEC: float = float(os.getenv("OLLAMA_TIMEOUT_SEC", "60"))
OLLAMA_MAX_RETRIES: int = int(os.getenv("OLLAMA_MAX_RETRIES", "3"))
OLLAMA_RETRY_BACKOFF_SEC: float = float(os.getenv("OLLAMA_RETRY_BACKOFF_SEC", "1"))

# ── Pipeline ──────────────────────────────────────────────────────────────────
# Number of notes committed per batch. Lower = less memory; higher = fewer round-trips.
EMBED_BATCH_SIZE: int = int(os.getenv("EMBED_BATCH_SIZE", "50"))

# Dimension guard — if the provider returns a different number of dims the row
# is rejected before writing to avoid silent schema corruption.
EMBED_EXPECTED_DIMS: int = int(os.getenv("EMBED_EXPECTED_DIMS", "768"))

