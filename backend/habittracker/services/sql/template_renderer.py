"""SQL template renderer — SqlTemplateRenderer.

SqlTemplateRenderer converts a (SqlAnalyticsIntent, SqlTemplateParams) pair
into a fully-formed, alias-free, parameterised SQL SELECT string.

Design principles:
  - Every template uses the full table name — no AS aliases.
  - Every template includes <table>.user_id = :user_id.
  - Every template includes a LIMIT clause.
  - Templates are plain Python f-strings, not SQLAlchemy constructs, so they
    are easy to read, test, and extend.
  - SqlTemplateRenderer.render() raises SqlTemplateError for unknown or
    unsupported intent values. Callers should treat that as a signal to fall
    back to LLM generation.
  - sql_template_renderer is the module-level singleton.
"""

from __future__ import annotations

from habittracker.schemas.sql_template import SqlAnalyticsIntent, SqlTemplateParams
from habittracker.services.sql.errors import SqlTemplateError

# Row limit applied to all template-rendered queries.
_TEMPLATE_LIMIT = 200


class SqlTemplateRenderer:
    """Renders fixed SQL templates from structured analytics parameters."""

    def render(self, params: SqlTemplateParams) -> str:
        """Return a parameterised SQL string for the given intent and params.

        Args:
            params: Structured parameters extracted from the user question.

        Returns:
            A SQL SELECT string ready for execution with {:user_id} bound.

        Raises:
            SqlTemplateError: The intent is UNKNOWN or has no template.
        """
        intent = params.intent

        if intent == SqlAnalyticsIntent.TOTAL_METRIC:
            return self._total_metric(params)

        if intent == SqlAnalyticsIntent.AVERAGE_PER_DAY:
            return self._average_per_day(params)

        if intent == SqlAnalyticsIntent.COUNT_LOGS:
            return self._count_logs(params)

        if intent == SqlAnalyticsIntent.DAILY_TREND:
            return self._daily_trend(params)

        if intent == SqlAnalyticsIntent.TOP_DAY:
            return self._top_day(params)

        if intent == SqlAnalyticsIntent.HABIT_COMPLETION_RATE:
            return self._habit_completion_rate(params)

        if intent == SqlAnalyticsIntent.COMPARE_PERIODS:
            return self._compare_periods(params)

        raise SqlTemplateError(
            f"No SQL template for intent '{intent}'. Use LLM generation fallback."
        )

    # ── Templates ─────────────────────────────────────────────────────────────

    @staticmethod
    def _total_metric(p: SqlTemplateParams) -> str:
        """Total SUM of a metric over a time window.

        Example: "How much water did I drink over the past 30 days?"
        """
        return (
            f"SELECT SUM({p.table}.{p.metric_col}) AS total_{p.metric_col}"
            f" FROM {p.table}"
            f" WHERE {p.table}.user_id = :user_id"
            f"   AND {p.table}.{p.ts_col} >= NOW() - INTERVAL '{p.interval_days} days'"
            f" LIMIT {_TEMPLATE_LIMIT}"
        )

    @staticmethod
    def _average_per_day(p: SqlTemplateParams) -> str:
        """Average of a metric per calendar day over a time window.

        Example: "What is my average water intake per day over the last 30 days?"
        """
        return (
            f"SELECT"
            f"  ROUND("
            f"    SUM({p.table}.{p.metric_col})"
            f"    / NULLIF(COUNT(DISTINCT DATE({p.table}.{p.ts_col})), 0),"
            f"  2) AS avg_{p.metric_col}_per_day"
            f" FROM {p.table}"
            f" WHERE {p.table}.user_id = :user_id"
            f"   AND {p.table}.{p.ts_col} >= NOW() - INTERVAL '{p.interval_days} days'"
            f" LIMIT {_TEMPLATE_LIMIT}"
        )

    @staticmethod
    def _count_logs(p: SqlTemplateParams) -> str:
        """Count of rows (events/logs) over a time window.

        Example: "How many bottle events did I log in the last 7 days?"
        """
        return (
            f"SELECT COUNT(*) AS event_count"
            f" FROM {p.table}"
            f" WHERE {p.table}.user_id = :user_id"
            f"   AND {p.table}.{p.ts_col} >= NOW() - INTERVAL '{p.interval_days} days'"
            f" LIMIT {_TEMPLATE_LIMIT}"
        )

    @staticmethod
    def _daily_trend(p: SqlTemplateParams) -> str:
        """Per-day breakdown of a metric over a time window.

        Example: "Show me my hydration day by day for the past 7 days."
        """
        date_expr = f"DATE({p.table}.{p.ts_col})"
        return (
            f"SELECT {date_expr} AS day,"
            f" SUM({p.table}.{p.metric_col}) AS total_{p.metric_col}"
            f" FROM {p.table}"
            f" WHERE {p.table}.user_id = :user_id"
            f"   AND {p.table}.{p.ts_col} >= NOW() - INTERVAL '{p.interval_days} days'"
            f" GROUP BY {date_expr}"
            f" ORDER BY day ASC"
            f" LIMIT {_TEMPLATE_LIMIT}"
        )

    @staticmethod
    def _top_day(p: SqlTemplateParams) -> str:
        """Single day with the highest total of a metric over a time window.

        Example: "Which day did I drink the most water in the last 30 days?"
        """
        date_expr = f"DATE({p.table}.{p.ts_col})"
        return (
            f"SELECT {date_expr} AS day,"
            f" SUM({p.table}.{p.metric_col}) AS total_{p.metric_col}"
            f" FROM {p.table}"
            f" WHERE {p.table}.user_id = :user_id"
            f"   AND {p.table}.{p.ts_col} >= NOW() - INTERVAL '{p.interval_days} days'"
            f" GROUP BY {date_expr}"
            f" ORDER BY total_{p.metric_col} DESC"
            f" LIMIT 1"
        )

    @staticmethod
    def _habit_completion_rate(p: SqlTemplateParams) -> str:
        """Habit completion rate: completed days / total days in window.

        Example: "What is my habit completion rate for the last 30 days?"
        """
        return (
            f"SELECT"
            f"  COUNT(DISTINCT habit_logs.logged_date) AS completed_days,"
            f"  {p.interval_days} AS window_days,"
            f"  ROUND("
            f"    COUNT(DISTINCT habit_logs.logged_date) * 100.0 / {p.interval_days},"
            f"  1) AS completion_pct"
            f" FROM habit_logs"
            f" JOIN habits ON habit_logs.habit_id = habits.id"
            f" WHERE habit_logs.user_id = :user_id"
            f"   AND habit_logs.logged_date >= CURRENT_DATE - INTERVAL '{p.interval_days} days'"
            f" LIMIT {_TEMPLATE_LIMIT}"
        )

    @staticmethod
    def _compare_periods(p: SqlTemplateParams) -> str:
        """Compare current period vs previous period of equal length.

        Example: "Compare my water intake this week vs last week."
        Half-window = interval_days / 2. If interval_days=14, compares
        0-7 days ago vs 7-14 days ago.

        Example: "Compare my water intake this week vs last week."
        """
        half = p.interval_days // 2
        return (
            f"SELECT"
            f"  SUM(CASE"
            f"    WHEN {p.table}.{p.ts_col} >= NOW() - INTERVAL '{half} days'"
            f"    THEN {p.table}.{p.metric_col} ELSE 0 END) AS current_period,"
            f"  SUM(CASE"
            f"    WHEN {p.table}.{p.ts_col} >= NOW() - INTERVAL '{p.interval_days} days'"
            f"      AND {p.table}.{p.ts_col} < NOW() - INTERVAL '{half} days'"
            f"    THEN {p.table}.{p.metric_col} ELSE 0 END) AS previous_period"
            f" FROM {p.table}"
            f" WHERE {p.table}.user_id = :user_id"
            f"   AND {p.table}.{p.ts_col} >= NOW() - INTERVAL '{p.interval_days} days'"
            f" LIMIT {_TEMPLATE_LIMIT}"
        )


# ── Module-level singleton ────────────────────────────────────────────────────

sql_template_renderer = SqlTemplateRenderer()
