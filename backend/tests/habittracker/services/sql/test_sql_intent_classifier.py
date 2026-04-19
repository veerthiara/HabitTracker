"""Tests for habittracker.services.sql.intent_classifier.

All tests are pure unit tests — no LLM or DB required.

Coverage areas:
  1. Each intent is returned for representative trigger phrases.
  2. UNKNOWN is returned when no keywords match.
  3. Evaluation order — COMPARE beats TOP_DAY when both keywords present.
  4. Case-insensitivity — mixed-case input routes correctly.
  5. Singleton — sql_intent_classifier is importable from the module.
"""

from __future__ import annotations

import pytest

from habittracker.schemas.sql_template import SqlAnalyticsIntent
from habittracker.services.sql.intent_classifier import SqlIntentClassifier, sql_intent_classifier


@pytest.fixture()
def clf() -> SqlIntentClassifier:
    return SqlIntentClassifier()


class TestIntentClassification:

    @pytest.mark.parametrize("question,expected", [
        # COMPARE_PERIODS
        ("Compare my water intake this week vs last week",   SqlAnalyticsIntent.COMPARE_PERIODS),
        ("Difference between this month and last month",      SqlAnalyticsIntent.COMPARE_PERIODS),
        # TOP_DAY
        ("Which day did I drink the most water?",             SqlAnalyticsIntent.TOP_DAY),
        ("What was my best day for hydration?",               SqlAnalyticsIntent.TOP_DAY),
        ("Which date had the highest volume?",                SqlAnalyticsIntent.TOP_DAY),
        # DAILY_TREND
        ("Show me my hydration day by day for the past 7 days", SqlAnalyticsIntent.DAILY_TREND),
        ("Give me a daily trend of my water intake",          SqlAnalyticsIntent.DAILY_TREND),
        # HABIT_COMPLETION_RATE
        ("What is my habit completion rate this month?",      SqlAnalyticsIntent.HABIT_COMPLETION_RATE),
        ("How often did I complete my morning habit?",        SqlAnalyticsIntent.HABIT_COMPLETION_RATE),
        # AVERAGE_PER_DAY
        ("What is my average water intake per day?",          SqlAnalyticsIntent.AVERAGE_PER_DAY),
        ("Tell me the average daily hydration last 30 days",  SqlAnalyticsIntent.AVERAGE_PER_DAY),
        # COUNT_LOGS
        ("How many times did I log water this week?",         SqlAnalyticsIntent.COUNT_LOGS),
        ("How many bottle events in the last 7 days?",        SqlAnalyticsIntent.COUNT_LOGS),
        # TOTAL_METRIC
        ("Total water I drank in the past 30 days",           SqlAnalyticsIntent.TOTAL_METRIC),
        ("How much water in total did I drink last week?",    SqlAnalyticsIntent.TOTAL_METRIC),
        # UNKNOWN
        ("hello",                                             SqlAnalyticsIntent.UNKNOWN),
        ("What is the weather today?",                        SqlAnalyticsIntent.UNKNOWN),
    ])
    def test_classification(self, clf: SqlIntentClassifier, question: str, expected: SqlAnalyticsIntent) -> None:
        assert clf.classify(question) == expected

    def test_case_insensitive(self, clf: SqlIntentClassifier) -> None:
        assert clf.classify("AVERAGE PER DAY WATER LAST 30 DAYS") == SqlAnalyticsIntent.AVERAGE_PER_DAY

    def test_compare_beats_top_day(self, clf: SqlIntentClassifier) -> None:
        # "vs" (compare) + "which day" (top_day) → compare wins because it is checked first
        assert clf.classify("which day had the most water vs last week") == SqlAnalyticsIntent.COMPARE_PERIODS


class TestSingleton:
    def test_singleton_is_instance(self) -> None:
        assert isinstance(sql_intent_classifier, SqlIntentClassifier)
