"""Tests for habittracker.services.sql.template_renderer.

All tests are pure unit tests — no LLM or DB required.

Coverage areas:
  1. Each intent renders a SQL string containing the expected tokens.
  2. No table aliases appear in any rendered SQL.
  3. Every rendered SQL contains <table>.user_id = :user_id.
  4. Every rendered SQL contains LIMIT.
  5. COMPARE_PERIODS uses the correct half-window arithmetic.
  6. UNKNOWN intent raises SqlTemplateError.
  7. Singleton is importable.
"""

from __future__ import annotations

import pytest

from habittracker.schemas.sql_template import SqlAnalyticsIntent, SqlTemplateParams
from habittracker.services.sql.errors import SqlTemplateError
from habittracker.services.sql.template_renderer import SqlTemplateRenderer, sql_template_renderer


def _params(intent: SqlAnalyticsIntent, **kwargs) -> SqlTemplateParams:
    defaults = dict(
        table="bottle_events",
        metric_col="volume_ml",
        ts_col="event_ts",
        interval_days=30,
    )
    defaults.update(kwargs)
    return SqlTemplateParams(intent=intent, **defaults)


@pytest.fixture()
def renderer() -> SqlTemplateRenderer:
    return SqlTemplateRenderer()


class TestTemplateTokens:
    """Each template must contain expected SQL tokens."""

    def test_total_metric_contains_sum(self, renderer: SqlTemplateRenderer) -> None:
        sql = renderer.render(_params(SqlAnalyticsIntent.TOTAL_METRIC))
        assert "SUM(bottle_events.volume_ml)" in sql

    def test_average_per_day_contains_round_and_nullif(self, renderer: SqlTemplateRenderer) -> None:
        sql = renderer.render(_params(SqlAnalyticsIntent.AVERAGE_PER_DAY))
        assert "ROUND(" in sql
        assert "NULLIF(" in sql

    def test_count_logs_contains_count_star(self, renderer: SqlTemplateRenderer) -> None:
        sql = renderer.render(_params(SqlAnalyticsIntent.COUNT_LOGS))
        assert "COUNT(*)" in sql

    def test_daily_trend_contains_group_by(self, renderer: SqlTemplateRenderer) -> None:
        sql = renderer.render(_params(SqlAnalyticsIntent.DAILY_TREND))
        assert "GROUP BY" in sql.upper()
        assert "ORDER BY" in sql.upper()

    def test_top_day_limit_1(self, renderer: SqlTemplateRenderer) -> None:
        sql = renderer.render(_params(SqlAnalyticsIntent.TOP_DAY))
        assert "LIMIT 1" in sql

    def test_habit_completion_rate_uses_habit_logs(self, renderer: SqlTemplateRenderer) -> None:
        sql = renderer.render(_params(SqlAnalyticsIntent.HABIT_COMPLETION_RATE))
        assert "habit_logs" in sql
        assert "habits" in sql

    def test_compare_periods_has_two_case_blocks(self, renderer: SqlTemplateRenderer) -> None:
        sql = renderer.render(_params(SqlAnalyticsIntent.COMPARE_PERIODS, interval_days=14))
        assert sql.upper().count("CASE") == 2

    def test_compare_periods_half_window(self, renderer: SqlTemplateRenderer) -> None:
        sql = renderer.render(_params(SqlAnalyticsIntent.COMPARE_PERIODS, interval_days=14))
        # half = 7  →  INTERVAL '7 days'  and  INTERVAL '14 days'
        assert "INTERVAL '7 days'" in sql
        assert "INTERVAL '14 days'" in sql


class TestSafetyInvariants:
    """Every rendered SQL must satisfy safety constraints."""

    ALL_INTENTS = [
        SqlAnalyticsIntent.TOTAL_METRIC,
        SqlAnalyticsIntent.AVERAGE_PER_DAY,
        SqlAnalyticsIntent.COUNT_LOGS,
        SqlAnalyticsIntent.DAILY_TREND,
        SqlAnalyticsIntent.TOP_DAY,
        SqlAnalyticsIntent.HABIT_COMPLETION_RATE,
        SqlAnalyticsIntent.COMPARE_PERIODS,
    ]

    @pytest.mark.parametrize("intent", ALL_INTENTS)
    def test_contains_user_id_filter(self, renderer: SqlTemplateRenderer, intent: SqlAnalyticsIntent) -> None:
        sql = renderer.render(_params(intent))
        assert ":user_id" in sql, f"Missing :user_id in {intent} template"
        assert "user_id" in sql.lower()

    @pytest.mark.parametrize("intent", ALL_INTENTS)
    def test_no_opaque_aliases(self, renderer: SqlTemplateRenderer, intent: SqlAnalyticsIntent) -> None:
        sql = renderer.render(_params(intent))
        for alias in (" AS T1", " AS T2", " AS t1", " AS t2", " AS be ", " AS hl "):
            assert alias not in sql, f"Alias {alias!r} found in {intent} template"

    @pytest.mark.parametrize("intent", ALL_INTENTS)
    def test_contains_limit(self, renderer: SqlTemplateRenderer, intent: SqlAnalyticsIntent) -> None:
        sql = renderer.render(_params(intent))
        assert "LIMIT" in sql.upper(), f"Missing LIMIT in {intent} template"

    @pytest.mark.parametrize("intent", ALL_INTENTS)
    def test_starts_with_select(self, renderer: SqlTemplateRenderer, intent: SqlAnalyticsIntent) -> None:
        sql = renderer.render(_params(intent)).lstrip()
        assert sql.upper().startswith("SELECT"), f"{intent} template does not start with SELECT"


class TestUnknownIntentRaises:
    def test_unknown_raises_template_error(self, renderer: SqlTemplateRenderer) -> None:
        with pytest.raises(SqlTemplateError):
            renderer.render(_params(SqlAnalyticsIntent.UNKNOWN))


class TestSingleton:
    def test_singleton_is_instance(self) -> None:
        assert isinstance(sql_template_renderer, SqlTemplateRenderer)
