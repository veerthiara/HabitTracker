"""Tests for chat_intent_service.classify_intent.

Pure function — no mocks, no session, no I/O.
"""

from habittracker.schemas.intent import ChatIntent
from habittracker.services.chat_intent_service import classify_intent


class TestClassifyIntentUnsupported:
    def test_single_greeting_is_unsupported(self):
        assert classify_intent("hello") == ChatIntent.UNSUPPORTED

    def test_casual_greeting_is_unsupported(self):
        assert classify_intent("hey") == ChatIntent.UNSUPPORTED

    def test_thanks_is_unsupported(self):
        assert classify_intent("thanks") == ChatIntent.UNSUPPORTED

    def test_single_char_is_unsupported(self):
        assert classify_intent("hi") == ChatIntent.UNSUPPORTED

    def test_three_chars_is_unsupported(self):
        # len < _MIN_MESSAGE_LEN (4) rule
        assert classify_intent("ok!") == ChatIntent.UNSUPPORTED

    def test_multi_word_all_unsupported_phrases_is_unsupported(self):
        assert classify_intent("yes okay") == ChatIntent.UNSUPPORTED

    def test_empty_string_is_unsupported(self):
        assert classify_intent("") == ChatIntent.UNSUPPORTED


class TestClassifyIntentBottleActivity:
    def test_water_keyword(self):
        assert classify_intent("How much water did I drink today?") == ChatIntent.BOTTLE_ACTIVITY

    def test_bottle_keyword(self):
        assert classify_intent("How many times did I pick up my bottle?") == ChatIntent.BOTTLE_ACTIVITY

    def test_hydration_keyword(self):
        assert classify_intent("Show me my hydration stats") == ChatIntent.BOTTLE_ACTIVITY

    def test_drink_keyword(self):
        assert classify_intent("Did I drink enough today?") == ChatIntent.BOTTLE_ACTIVITY

    def test_ml_keyword(self):
        assert classify_intent("How many ml have I had?") == ChatIntent.BOTTLE_ACTIVITY

    def test_case_insensitive(self):
        assert classify_intent("WATER consumption today") == ChatIntent.BOTTLE_ACTIVITY


class TestClassifyIntentHabitSummary:
    def test_habit_keyword(self):
        assert classify_intent("What habits did I complete today?") == ChatIntent.HABIT_SUMMARY

    def test_routine_keyword(self):
        assert classify_intent("How is my morning routine going?") == ChatIntent.HABIT_SUMMARY

    def test_completed_keyword(self):
        assert classify_intent("Which ones have I completed so far?") == ChatIntent.HABIT_SUMMARY

    def test_tracked_keyword(self):
        assert classify_intent("What have I tracked today?") == ChatIntent.HABIT_SUMMARY

    def test_streak_keyword(self):
        assert classify_intent("What is my current streak?") == ChatIntent.HABIT_SUMMARY


class TestClassifyIntentNotePattern:
    def test_why_keyword(self):
        # No bottle or habit keywords — "why" alone routes to NOTE_PATTERN.
        assert classify_intent("Why do I keep writing the same things in my journal?") == ChatIntent.NOTE_PATTERN

    def test_pattern_keyword(self):
        assert classify_intent("What patterns do you see in my notes?") == ChatIntent.NOTE_PATTERN

    def test_trend_keyword(self):
        assert classify_intent("Is there a trend in my behaviour?") == ChatIntent.NOTE_PATTERN

    def test_often_keyword(self):
        assert classify_intent("How often do I write about being tired?") == ChatIntent.NOTE_PATTERN

    def test_usually_keyword(self):
        assert classify_intent("What do I usually say after a bad day?") == ChatIntent.NOTE_PATTERN


class TestClassifyIntentSqlAnalytics:
    def test_which_day_routes_to_sql(self):
        # No bottle or habit keyword — "which day" alone routes to SQL_ANALYTICS.
        assert classify_intent("Which day had the highest overall activity?") == ChatIntent.SQL_ANALYTICS

    def test_average_keyword(self):
        assert classify_intent("What is my average daily completion per week?") == ChatIntent.SQL_ANALYTICS

    def test_compare_keyword(self):
        assert classify_intent("Compare this week vs last week") == ChatIntent.SQL_ANALYTICS

    def test_top_keyword(self):
        assert classify_intent("What are the top performing days this month?") == ChatIntent.SQL_ANALYTICS

    def test_by_weekday(self):
        assert classify_intent("Show my activity broken down by weekday") == ChatIntent.SQL_ANALYTICS

    def test_highest_keyword(self):
        assert classify_intent("Which day has the highest completion rate?") == ChatIntent.SQL_ANALYTICS

    def test_breakdown_keyword(self):
        assert classify_intent("Give me a breakdown of my daily activity") == ChatIntent.SQL_ANALYTICS

    def test_over_the_last_keyword(self):
        assert classify_intent("How many logs over the last 30 days?") == ChatIntent.SQL_ANALYTICS

    def test_most_often_keyword(self):
        # "often" alone (NOTE_PATTERN) is checked before SQL, so test a
        # clean SQL-only keyword instead.
        assert classify_intent("How many logs do I make per week?") == ChatIntent.SQL_ANALYTICS


class TestClassifyIntentGeneral:
    def test_unknown_question_falls_back_to_general(self):
        assert classify_intent("Tell me something about my progress") == ChatIntent.GENERAL

    def test_open_ended_question_is_general(self):
        assert classify_intent("Give me a summary of everything") == ChatIntent.GENERAL

    def test_long_sentence_no_keywords_is_general(self):
        assert classify_intent("I would like to know more about my overall situation") == ChatIntent.GENERAL


class TestClassifyIntentOrdering:
    """Verify evaluation order: SQL_ANALYTICS > BOTTLE > HABIT > NOTE_PATTERN.

    When a message contains keywords from multiple intent groups, the
    higher-priority group wins.  This prevents surprising misrouting.

    SQL_ANALYTICS is first because aggregation/time-range keywords are specific
    enough to unambiguously signal analytics even when the message also mentions
    domain entities (water, habit).  Simple lookup questions ("how much today?")
    have no SQL keywords and still fall through to BOTTLE/HABIT.
    """

    def test_sql_beats_bottle_when_analytical(self):
        # "average", "last 30", "per day" are SQL keywords; "water" is bottle.
        # SQL is checked first so SQL_ANALYTICS must win.
        assert classify_intent("Tell me in last 30 days average water drank per day") == ChatIntent.SQL_ANALYTICS

    def test_sql_beats_habit_when_analytical(self):
        # "average" + "per day" override "habit".
        assert classify_intent("What is my average habit completion per day this month?") == ChatIntent.SQL_ANALYTICS

    def test_bottle_beats_habit_when_both_present(self):
        # "water" is a bottle keyword — should win even if "habit" is also present.
        assert classify_intent("Did I drink water after my morning habit?") == ChatIntent.BOTTLE_ACTIVITY

    def test_bottle_beats_pattern_when_both_present(self):
        assert classify_intent("Why is my water intake low?") == ChatIntent.BOTTLE_ACTIVITY

    def test_habit_beats_pattern_when_both_present(self):
        # "habit" should win over "why" since habit is checked before pattern.
        assert classify_intent("Why did I miss my habit today?") == ChatIntent.HABIT_SUMMARY


class TestClassifyIntentReturnType:
    """Ensure the classifier returns ChatIntent enum members, not raw strings."""

    def test_return_is_chat_intent_instance(self):
        result = classify_intent("How much water did I drink?")
        assert isinstance(result, ChatIntent)

    def test_enum_value_matches_string(self):
        # StrEnum — the value is also a valid string for JSON serialisation.
        result = classify_intent("How much water did I drink?")
        assert result == "bottle_activity"
        assert result.value == "bottle_activity"
