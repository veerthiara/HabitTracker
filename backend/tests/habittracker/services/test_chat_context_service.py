"""Tests for chat_context_service.gather_context.

Uses unittest.mock to patch repositories and embedding helpers so no
database or Ollama connection is required.

Patch targets are the names as imported into chat_context_service, not
the original module paths.

Stacked @patch decorators: the bottom decorator's mock is the first
positional argument after self.
"""

import uuid
from unittest.mock import MagicMock, patch

from habittracker.providers.base import EmbeddingError
from habittracker.schemas.chat import EvidenceItem
from habittracker.schemas.intent import ChatIntent
from habittracker.services.chat_context_service import (
    ChatContextResult,
    gather_context,
)

USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_session():
    return MagicMock()


def _make_embed_provider():
    return MagicMock()


def _make_bottle_event(volume_ml: int = 300):
    event = MagicMock()
    event.volume_ml = volume_ml
    event.event_ts = MagicMock()
    event.event_ts.strftime.return_value = "10:00"
    return event


def _make_dashboard_summary(total: int = 3, done: int = 2, hydration_ml: int = 900):
    summary = MagicMock()
    summary.habits_total = total
    summary.habits_done_today = done
    summary.hydration_today_ml = hydration_ml

    hs1 = MagicMock()
    hs1.done_today = True
    hs1.habit.name = "Morning run"
    hs1.habit.frequency = "daily"

    hs2 = MagicMock()
    hs2.done_today = False
    hs2.habit.name = "Meditate"
    hs2.habit.frequency = "daily"

    summary.habit_summaries = [hs1, hs2]
    return summary


def _make_note_row(content: str = "Felt great today", score: float = 0.85):
    row = MagicMock()
    row.id = uuid.uuid4()
    row.content = content
    row.score = score
    return row


# ── ChatContextResult structure ───────────────────────────────────────────────


class TestChatContextResultDefaults:
    def test_default_evidence_is_empty_list(self):
        result = ChatContextResult()
        assert result.evidence == []

    def test_default_context_text_is_empty_string(self):
        result = ChatContextResult()
        assert result.context_text == ""

    def test_default_used_notes_is_false(self):
        result = ChatContextResult()
        assert result.used_notes is False


# ── UNSUPPORTED ───────────────────────────────────────────────────────────────


class TestGatherContextUnsupported:
    @patch("habittracker.services.chat_context_service.bottle_event_repository")
    @patch("habittracker.services.chat_context_service.dashboard_repository")
    @patch("habittracker.services.chat_context_service.embed_query")
    def test_unsupported_returns_empty_result(self, mock_embed, mock_dash, mock_bottle):
        result = gather_context(
            _make_session(), USER_ID, ChatIntent.UNSUPPORTED, "hello", _make_embed_provider()
        )
        assert result == ChatContextResult()

    @patch("habittracker.services.chat_context_service.bottle_event_repository")
    @patch("habittracker.services.chat_context_service.dashboard_repository")
    @patch("habittracker.services.chat_context_service.embed_query")
    def test_unsupported_calls_no_repos(self, mock_embed, mock_dash, mock_bottle):
        gather_context(
            _make_session(), USER_ID, ChatIntent.UNSUPPORTED, "hello", _make_embed_provider()
        )
        mock_bottle.get_events.assert_not_called()
        mock_dash.get_summary.assert_not_called()
        mock_embed.assert_not_called()


# ── BOTTLE_ACTIVITY ───────────────────────────────────────────────────────────


class TestGatherContextBottleActivity:
    @patch("habittracker.services.chat_context_service.embed_query")
    @patch("habittracker.services.chat_context_service.dashboard_repository")
    @patch("habittracker.services.chat_context_service.bottle_event_repository")
    def test_calls_bottle_repo(self, mock_bottle, mock_dash, mock_embed):
        mock_bottle.get_events.return_value = []
        gather_context(
            _make_session(), USER_ID, ChatIntent.BOTTLE_ACTIVITY, "how much water?", _make_embed_provider()
        )
        assert mock_bottle.get_events.call_count == 1

    @patch("habittracker.services.chat_context_service.embed_query")
    @patch("habittracker.services.chat_context_service.dashboard_repository")
    @patch("habittracker.services.chat_context_service.bottle_event_repository")
    def test_does_not_call_embed(self, mock_bottle, mock_dash, mock_embed):
        mock_bottle.get_events.return_value = []
        gather_context(
            _make_session(), USER_ID, ChatIntent.BOTTLE_ACTIVITY, "how much water?", _make_embed_provider()
        )
        mock_embed.assert_not_called()

    @patch("habittracker.services.chat_context_service.embed_query")
    @patch("habittracker.services.chat_context_service.dashboard_repository")
    @patch("habittracker.services.chat_context_service.bottle_event_repository")
    def test_used_notes_is_false(self, mock_bottle, mock_dash, mock_embed):
        mock_bottle.get_events.return_value = []
        result = gather_context(
            _make_session(), USER_ID, ChatIntent.BOTTLE_ACTIVITY, "water", _make_embed_provider()
        )
        assert result.used_notes is False

    @patch("habittracker.services.chat_context_service.embed_query")
    @patch("habittracker.services.chat_context_service.dashboard_repository")
    @patch("habittracker.services.chat_context_service.bottle_event_repository")
    def test_evidence_contains_pickup_and_volume_metrics(self, mock_bottle, mock_dash, mock_embed):
        mock_bottle.get_events.return_value = [
            _make_bottle_event(300),
            _make_bottle_event(500),
        ]
        result = gather_context(
            _make_session(), USER_ID, ChatIntent.BOTTLE_ACTIVITY, "water", _make_embed_provider()
        )
        labels = [e.label for e in result.evidence]
        assert "Bottle pickups today" in labels
        assert "Total hydration today" in labels

    @patch("habittracker.services.chat_context_service.embed_query")
    @patch("habittracker.services.chat_context_service.dashboard_repository")
    @patch("habittracker.services.chat_context_service.bottle_event_repository")
    def test_total_volume_sums_events(self, mock_bottle, mock_dash, mock_embed):
        mock_bottle.get_events.return_value = [
            _make_bottle_event(300),
            _make_bottle_event(500),
        ]
        result = gather_context(
            _make_session(), USER_ID, ChatIntent.BOTTLE_ACTIVITY, "water", _make_embed_provider()
        )
        volume_item = next(e for e in result.evidence if e.label == "Total hydration today")
        assert "800" in volume_item.value

    @patch("habittracker.services.chat_context_service.embed_query")
    @patch("habittracker.services.chat_context_service.dashboard_repository")
    @patch("habittracker.services.chat_context_service.bottle_event_repository")
    def test_context_text_contains_date(self, mock_bottle, mock_dash, mock_embed):
        mock_bottle.get_events.return_value = []
        result = gather_context(
            _make_session(), USER_ID, ChatIntent.BOTTLE_ACTIVITY, "water", _make_embed_provider()
        )
        assert "Hydration summary for" in result.context_text


# ── HABIT_SUMMARY ─────────────────────────────────────────────────────────────


class TestGatherContextHabitSummary:
    @patch("habittracker.services.chat_context_service.embed_query")
    @patch("habittracker.services.chat_context_service.bottle_event_repository")
    @patch("habittracker.services.chat_context_service.dashboard_repository")
    def test_calls_dashboard_repo(self, mock_dash, mock_bottle, mock_embed):
        mock_dash.get_summary.return_value = _make_dashboard_summary()
        gather_context(
            _make_session(), USER_ID, ChatIntent.HABIT_SUMMARY, "habits?", _make_embed_provider()
        )
        assert mock_dash.get_summary.call_count == 1

    @patch("habittracker.services.chat_context_service.embed_query")
    @patch("habittracker.services.chat_context_service.bottle_event_repository")
    @patch("habittracker.services.chat_context_service.dashboard_repository")
    def test_does_not_call_embed(self, mock_dash, mock_bottle, mock_embed):
        mock_dash.get_summary.return_value = _make_dashboard_summary()
        gather_context(
            _make_session(), USER_ID, ChatIntent.HABIT_SUMMARY, "habits?", _make_embed_provider()
        )
        mock_embed.assert_not_called()

    @patch("habittracker.services.chat_context_service.embed_query")
    @patch("habittracker.services.chat_context_service.bottle_event_repository")
    @patch("habittracker.services.chat_context_service.dashboard_repository")
    def test_used_notes_is_false(self, mock_dash, mock_bottle, mock_embed):
        mock_dash.get_summary.return_value = _make_dashboard_summary()
        result = gather_context(
            _make_session(), USER_ID, ChatIntent.HABIT_SUMMARY, "habits?", _make_embed_provider()
        )
        assert result.used_notes is False

    @patch("habittracker.services.chat_context_service.embed_query")
    @patch("habittracker.services.chat_context_service.bottle_event_repository")
    @patch("habittracker.services.chat_context_service.dashboard_repository")
    def test_evidence_contains_metric_and_habit_items(self, mock_dash, mock_bottle, mock_embed):
        mock_dash.get_summary.return_value = _make_dashboard_summary()
        result = gather_context(
            _make_session(), USER_ID, ChatIntent.HABIT_SUMMARY, "habits?", _make_embed_provider()
        )
        types = [e.type for e in result.evidence]
        assert "metric" in types
        assert "habit" in types

    @patch("habittracker.services.chat_context_service.embed_query")
    @patch("habittracker.services.chat_context_service.bottle_event_repository")
    @patch("habittracker.services.chat_context_service.dashboard_repository")
    def test_context_text_contains_habit_summary(self, mock_dash, mock_bottle, mock_embed):
        mock_dash.get_summary.return_value = _make_dashboard_summary()
        result = gather_context(
            _make_session(), USER_ID, ChatIntent.HABIT_SUMMARY, "habits?", _make_embed_provider()
        )
        assert "Habit summary for" in result.context_text
        assert "Morning run" in result.context_text


# ── NOTE_PATTERN ──────────────────────────────────────────────────────────────


class TestGatherContextNotePattern:
    @patch("habittracker.services.chat_context_service.search_notes")
    @patch("habittracker.services.chat_context_service.embed_query")
    def test_calls_embed_and_search(self, mock_embed, mock_search):
        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = [_make_note_row()]
        gather_context(
            _make_session(), USER_ID, ChatIntent.NOTE_PATTERN, "why this pattern?", _make_embed_provider()
        )
        assert mock_embed.call_count == 1
        assert mock_search.call_count == 1

    @patch("habittracker.services.chat_context_service.search_notes")
    @patch("habittracker.services.chat_context_service.embed_query")
    def test_used_notes_is_true_when_rows_found(self, mock_embed, mock_search):
        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = [_make_note_row()]
        result = gather_context(
            _make_session(), USER_ID, ChatIntent.NOTE_PATTERN, "why?", _make_embed_provider()
        )
        assert result.used_notes is True

    @patch("habittracker.services.chat_context_service.search_notes")
    @patch("habittracker.services.chat_context_service.embed_query")
    def test_empty_search_returns_empty_result(self, mock_embed, mock_search):
        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = []
        result = gather_context(
            _make_session(), USER_ID, ChatIntent.NOTE_PATTERN, "why?", _make_embed_provider()
        )
        assert result == ChatContextResult()

    @patch("habittracker.services.chat_context_service.search_notes")
    @patch("habittracker.services.chat_context_service.embed_query")
    def test_evidence_has_note_items(self, mock_embed, mock_search):
        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = [_make_note_row("Tired after lunch"), _make_note_row("Long day")]
        result = gather_context(
            _make_session(), USER_ID, ChatIntent.NOTE_PATTERN, "why?", _make_embed_provider()
        )
        assert len(result.evidence) == 2
        assert all(e.type == "note" for e in result.evidence)

    @patch("habittracker.services.chat_context_service.search_notes")
    @patch("habittracker.services.chat_context_service.embed_query")
    def test_context_text_contains_score(self, mock_embed, mock_search):
        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = [_make_note_row(score=0.91)]
        result = gather_context(
            _make_session(), USER_ID, ChatIntent.NOTE_PATTERN, "why?", _make_embed_provider()
        )
        assert "0.91" in result.context_text

    @patch("habittracker.services.chat_context_service.dashboard_repository")
    @patch("habittracker.services.chat_context_service.bottle_event_repository")
    @patch("habittracker.services.chat_context_service.search_notes")
    @patch("habittracker.services.chat_context_service.embed_query")
    def test_does_not_call_data_repos(self, mock_embed, mock_search, mock_bottle, mock_dash):
        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = [_make_note_row()]
        gather_context(
            _make_session(), USER_ID, ChatIntent.NOTE_PATTERN, "why?", _make_embed_provider()
        )
        mock_bottle.get_events.assert_not_called()
        mock_dash.get_summary.assert_not_called()


# ── GENERAL ───────────────────────────────────────────────────────────────────


class TestGatherContextGeneral:
    @patch("habittracker.services.chat_context_service.search_notes")
    @patch("habittracker.services.chat_context_service.embed_query")
    @patch("habittracker.services.chat_context_service.dashboard_repository")
    def test_calls_dashboard_and_search(self, mock_dash, mock_embed, mock_search):
        mock_dash.get_summary.return_value = _make_dashboard_summary()
        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = [_make_note_row()]
        gather_context(
            _make_session(), USER_ID, ChatIntent.GENERAL, "anything?", _make_embed_provider()
        )
        assert mock_dash.get_summary.call_count == 1
        assert mock_embed.call_count == 1

    @patch("habittracker.services.chat_context_service.search_notes")
    @patch("habittracker.services.chat_context_service.embed_query")
    @patch("habittracker.services.chat_context_service.dashboard_repository")
    def test_used_notes_true_when_notes_found(self, mock_dash, mock_embed, mock_search):
        mock_dash.get_summary.return_value = _make_dashboard_summary()
        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = [_make_note_row()]
        result = gather_context(
            _make_session(), USER_ID, ChatIntent.GENERAL, "anything?", _make_embed_provider()
        )
        assert result.used_notes is True

    @patch("habittracker.services.chat_context_service.search_notes")
    @patch("habittracker.services.chat_context_service.embed_query")
    @patch("habittracker.services.chat_context_service.dashboard_repository")
    def test_used_notes_false_when_no_notes(self, mock_dash, mock_embed, mock_search):
        mock_dash.get_summary.return_value = _make_dashboard_summary()
        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = []
        result = gather_context(
            _make_session(), USER_ID, ChatIntent.GENERAL, "anything?", _make_embed_provider()
        )
        assert result.used_notes is False

    @patch("habittracker.services.chat_context_service.search_notes")
    @patch("habittracker.services.chat_context_service.embed_query")
    @patch("habittracker.services.chat_context_service.dashboard_repository")
    def test_embedding_error_degrades_gracefully(self, mock_dash, mock_embed, mock_search):
        mock_dash.get_summary.return_value = _make_dashboard_summary()
        mock_embed.side_effect = EmbeddingError("Ollama down")
        result = gather_context(
            _make_session(), USER_ID, ChatIntent.GENERAL, "anything?", _make_embed_provider()
        )
        # Dashboard data still returned, embedding failure doesn't break the flow
        assert result.used_notes is False
        assert any(e.type == "metric" for e in result.evidence)
        assert mock_search.call_count == 0

    @patch("habittracker.services.chat_context_service.search_notes")
    @patch("habittracker.services.chat_context_service.embed_query")
    @patch("habittracker.services.chat_context_service.dashboard_repository")
    def test_context_text_contains_overview(self, mock_dash, mock_embed, mock_search):
        mock_dash.get_summary.return_value = _make_dashboard_summary()
        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = []
        result = gather_context(
            _make_session(), USER_ID, ChatIntent.GENERAL, "anything?", _make_embed_provider()
        )
        assert "Today's overview" in result.context_text

    @patch("habittracker.services.chat_context_service.search_notes")
    @patch("habittracker.services.chat_context_service.embed_query")
    @patch("habittracker.services.chat_context_service.dashboard_repository")
    def test_general_evidence_includes_note_items_when_found(self, mock_dash, mock_embed, mock_search):
        mock_dash.get_summary.return_value = _make_dashboard_summary()
        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = [_make_note_row("Some insight")]
        result = gather_context(
            _make_session(), USER_ID, ChatIntent.GENERAL, "anything?", _make_embed_provider()
        )
        note_items = [e for e in result.evidence if e.type == "note"]
        assert len(note_items) == 1
