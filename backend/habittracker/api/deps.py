"""Shared FastAPI dependencies."""
import uuid

# ---------------------------------------------------------------------------
# Auth placeholder
# Phase 03 has no authentication. All requests are treated as the single demo
# user created by the seed script. Replace this with a real JWT dependency in
# a future phase.
# ---------------------------------------------------------------------------
DEMO_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def get_current_user_id() -> uuid.UUID:
    """Return the active user ID (hardcoded until auth is implemented)."""
    return DEMO_USER_ID
