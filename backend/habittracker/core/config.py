"""Shared Ollama and embedding/chat configuration.

Settings here are consumed by both the FastAPI application layer
(habittracker/) and the CLI scripts (scripts/embed/).

All values are read from environment variables so no code changes
are needed to reconfigure — just export a different env var.

Environment variables:
    OLLAMA_BASE_URL          — Ollama server URL (default: http://localhost:11434)
    OLLAMA_EMBED_MODEL       — Model for embeddings (default: nomic-embed-text)
    OLLAMA_CHAT_MODEL        — Model for chat/completion (default: llama3.2)
    OLLAMA_TIMEOUT_SEC       — HTTP timeout for embedding requests in seconds (default: 60)
    OLLAMA_CHAT_TIMEOUT_SEC  — HTTP timeout for chat/completion requests in seconds (default: 120)
    OLLAMA_MAX_RETRIES       — Retry count on transient failures (default: 3)
    OLLAMA_RETRY_BACKOFF_SEC — Initial backoff in seconds; doubles each retry (default: 1)
    EMBED_BATCH_SIZE         — Notes per commit batch in the pipeline (default: 50)
    EMBED_EXPECTED_DIMS      — Expected vector dimensions; mismatches are rejected (default: 768)

Langfuse observability (optional — see core/langfuse_integration.py):
    LANGFUSE_PUBLIC_KEY      — Langfuse project public key (required to enable)
    LANGFUSE_SECRET_KEY      — Langfuse project secret key (required to enable)
    LANGFUSE_BASE_URL        — Langfuse server URL (required; e.g. http://localhost:3000)
    LANGFUSE_TRACING_ENABLED — Set to "false" to disable tracing (default: "true")

SQL analytics execution:
    SQL_MAX_ROWS             — Hard row cap for analytics queries (default: 200)
    SQL_STATEMENT_TIMEOUT_MS — Per-query Postgres timeout in ms (default: 5000)
"""

import os

# ── Ollama — shared ───────────────────────────────────────────────────────────
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MAX_RETRIES: int = int(os.getenv("OLLAMA_MAX_RETRIES", "3"))
OLLAMA_RETRY_BACKOFF_SEC: float = float(os.getenv("OLLAMA_RETRY_BACKOFF_SEC", "1"))

# ── Ollama — embedding ────────────────────────────────────────────────────────
OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_TIMEOUT_SEC: float = float(os.getenv("OLLAMA_TIMEOUT_SEC", "60"))

# ── Ollama — chat/completion ──────────────────────────────────────────────────
OLLAMA_CHAT_MODEL: str = os.getenv("OLLAMA_CHAT_MODEL", "qwen2.5-coder:7b")
OLLAMA_CHAT_TIMEOUT_SEC: float = float(os.getenv("OLLAMA_CHAT_TIMEOUT_SEC", "120"))

# ── Pipeline ──────────────────────────────────────────────────────────────────
EMBED_BATCH_SIZE: int = int(os.getenv("EMBED_BATCH_SIZE", "50"))
EMBED_EXPECTED_DIMS: int = int(os.getenv("EMBED_EXPECTED_DIMS", "768"))

# ── Conversation memory ───────────────────────────────────────────────────────
# Maximum number of ConversationTurn entries fed to the LLM per request.
# Each user+assistant pair = 2 entries, so 10 entries = 5 prior exchanges.
# Older turns remain in the MemorySaver checkpoint but are not sent to the LLM.
# Override via the CONVERSATION_WINDOW env var to tune without code changes.
CONVERSATION_WINDOW: int = int(os.getenv("CONVERSATION_WINDOW", "10"))

# ── SQL analytics execution ───────────────────────────────────────────────────
# Hard cap on result rows returned from analytics queries. Prevents the LLM
# from receiving an arbitrarily large payload and keeps response latency low.
SQL_MAX_ROWS: int = int(os.getenv("SQL_MAX_ROWS", "200"))

# Per-query Postgres statement_timeout in milliseconds. Ensures a slow
# generated query cannot stall the application server.
SQL_STATEMENT_TIMEOUT_MS: int = int(os.getenv("SQL_STATEMENT_TIMEOUT_MS", "5000"))
