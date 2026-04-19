"""Pydantic models for the template-backed SQL path (Rev 08).

These models define the structured parameters extracted from a user question
before rendering a fixed SQL template.  They are internal contracts between
SqlIntentClassifier, SqlParameterExtractor, and SqlTemplateRenderer.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SqlAnalyticsIntent(str, Enum):
    """Known SQL analytics question families that map to fixed templates.

    UNKNOWN means the question did not match any template pattern and must
    fall back to free-form LLM SQL generation.
    """

    TOTAL_METRIC = "total_metric"
    AVERAGE_PER_DAY = "average_per_day"
    COUNT_LOGS = "count_logs"
    DAILY_TREND = "daily_trend"
    TOP_DAY = "top_day"
    HABIT_COMPLETION_RATE = "habit_completion_rate"
    COMPARE_PERIODS = "compare_periods"
    UNKNOWN = "unknown"


class SqlTemplateParams(BaseModel):
    """Structured parameters extracted from a natural-language analytics question.

    Used by SqlTemplateRenderer to fill in a fixed SQL template.
    All parameters are optional because not every template needs all of them.
    """

    intent: SqlAnalyticsIntent = Field(..., description="Classified template intent.")
    table: str = Field(
        default="bottle_events",
        description="Primary table to query (must be in approved schema).",
    )
    metric_col: str = Field(
        default="volume_ml",
        description="Column to aggregate (SUM, AVG, COUNT).",
    )
    interval_days: int = Field(
        default=30,
        description="Time window in days (7, 30, 90, etc.).",
    )
    ts_col: str = Field(
        default="event_ts",
        description="Timestamp/date column used for time-range filtering.",
    )
    grouping_col: str | None = Field(
        default=None,
        description="Optional column to GROUP BY (e.g. DATE(event_ts), logged_date).",
    )
    habit_name: str | None = Field(
        default=None,
        description="Habit name filter, used by HABIT_COMPLETION_RATE.",
    )
