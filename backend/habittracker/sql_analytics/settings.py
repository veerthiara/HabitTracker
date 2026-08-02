"""Generic SQL Analytics Settings.

Configuration for the SQL analytics core.
Uses existing config conventions from habittracker.core.config.
"""

import os
from pydantic import BaseModel, Field, model_validator


class SqlAnalyticsSettings(BaseModel):
    """Typed settings for SQL analytics behavior."""

    enabled: bool = True
    default_limit: int = Field(default=50, ge=1)
    max_rows: int = Field(default=100, ge=1)
    statement_timeout_ms: int = Field(default=5000, ge=1)
    max_result_chars: int = Field(default=20000, ge=1)
    debug_responses: bool = False
    allow_note_content: bool = False

    @model_validator(mode="after")
    def _validate_limits(self) -> "SqlAnalyticsSettings":
        if self.default_limit > self.max_rows:
            raise ValueError("default_limit must be <= max_rows")
        return self


def _load_settings() -> SqlAnalyticsSettings:
    """Load settings from environment variables with defaults."""
    return SqlAnalyticsSettings(
        enabled=os.getenv("SQL_QA_ENABLED", "true").lower() == "true",
        default_limit=int(os.getenv("SQL_QA_DEFAULT_LIMIT", "50")),
        max_rows=int(os.getenv("SQL_QA_MAX_ROWS", "100")),
        statement_timeout_ms=int(os.getenv("SQL_QA_STATEMENT_TIMEOUT_MS", "5000")),
        max_result_chars=int(os.getenv("SQL_QA_MAX_RESULT_CHARS", "20000")),
        debug_responses=os.getenv("SQL_QA_DEBUG_RESPONSES", "false").lower() == "true",
        allow_note_content=os.getenv("SQL_QA_ALLOW_NOTE_CONTENT", "false").lower() == "true",
    )


# Global settings instance
SETTINGS = _load_settings()


def get_settings() -> SqlAnalyticsSettings:
    """Get the current settings instance."""
    return SETTINGS