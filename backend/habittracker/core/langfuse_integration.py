"""Optional Langfuse observability integration.

Provides a LangChain/LangGraph callback handler that sends trace data to a
Langfuse server.  Tracing is **opt-in**: it activates only when the required
environment variables are set.

Required environment variables (all three must be present to enable tracing):
    LANGFUSE_PUBLIC_KEY  — Project public key from Langfuse settings.
    LANGFUSE_SECRET_KEY  — Project secret key from Langfuse settings.
    LANGFUSE_BASE_URL    — Langfuse server URL (e.g. http://localhost:3000 for
                           local, or https://cloud.langfuse.com for hosted).

Optional environment variables:
    LANGFUSE_TRACING_ENABLED — Set to "false" to disable even when keys are
                               present (default: "true").

When tracing is disabled (keys missing or explicitly turned off), every
helper in this module returns ``None`` so callers can simply check for
truthiness without branching on imports.
"""

import logging
import os

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

LANGFUSE_PUBLIC_KEY: str | None = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY: str | None = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_BASE_URL: str | None = os.getenv("LANGFUSE_BASE_URL")

_TRACING_ENABLED: bool = (
    os.getenv("LANGFUSE_TRACING_ENABLED", "true").lower() != "false"
)

_langfuse_available: bool = bool(
    LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY and LANGFUSE_BASE_URL and _TRACING_ENABLED
)


def is_langfuse_enabled() -> bool:
    """Return True when Langfuse tracing is fully configured and enabled."""
    return _langfuse_available


def get_langfuse_callback_handler():
    """Return a Langfuse LangChain CallbackHandler, or ``None`` if disabled.

    The handler is created fresh per call so that each request gets its own
    trace context.  This is the recommended pattern for web frameworks.

    In Langfuse v4 the handler reads ``LANGFUSE_PUBLIC_KEY``,
    ``LANGFUSE_SECRET_KEY``, and ``LANGFUSE_BASE_URL`` from the environment
    automatically — no explicit constructor arguments are needed.

    Returns:
        A ``LangchainCallbackHandler`` instance when tracing is enabled,
        ``None`` otherwise.
    """
    if not _langfuse_available:
        return None

    try:
        from langfuse.langchain import CallbackHandler

        handler = CallbackHandler()
        return handler
    except Exception:
        logger.warning("Failed to create Langfuse callback handler", exc_info=True)
        return None


# Log status at import time so operators know whether tracing is active.
if _langfuse_available:
    logger.info(
        "Langfuse tracing enabled (base_url=%s)",
        LANGFUSE_BASE_URL,
    )
else:
    logger.debug("Langfuse tracing disabled (missing env vars or explicitly off)")
