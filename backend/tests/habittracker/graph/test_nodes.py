"""Tests for graph/nodes.py — unit tests for each graph node in isolation.

Each node is tested independently with mocked dependencies so no real
database, embedding model, or LLM is needed.

Test coverage:
  classify_intent_node  — pure function, no mocks required
  gather_context_node   — session + embed_provider mocked via monkeypatch
  generate_answer_node  — chat_provider mocked via unittest.mock
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from habittracker.graph.nodes import (
    classify_intent_node,
    make_gather_context_node,
    make_generate_answer_node,
)
from habittracker.schemas.chat import EvidenceItem
from habittracker.schemas.intent import ChatIntent
from habittracker.services.chat_context_service import ChatContextResult
from habittracker.services.chat_service import FALLBACK_ANSWER, MAX_ANSWER_LEN


# ── classify_intent_node ──────────────────────────────────────────────────────

class TestClassifyIntentNode:
    def test_bottle_message(self):
        state = {"message": "How much water did I drink today?"}
        result = classify_intent_node(state)
        assert result == {"intent": "bottle_activity"}

    def test_habit_message(self):
        state = {"message": "Did I complete my morning habit?"}
        result = classify_intent_node(state)
        assert result == {"intent": "habit_summary"}

    def test_note_pattern_message(self):
        # "habit" is checked before "why" in the classifier, so the message
        # must not contain habit keywords to reach NOTE_PATTERN.
        state = {"message": "Why do I always feel tired on Fridays?"}
        result = classify_intent_node(state)
        assert result == {"intent": "note_pattern_question"}

    def test_general_message(self):
        state = {"message": "Give me a summary of my week"}
        result = classify_intent_node(state)
        assert result == {"intent": "general_question"}

    def test_unsupported_greeting(self):
        state = {"message": "hello"}
        result = classify_intent_node(state)
        assert result == {"intent": "unsupported"}

    def test_returns_string_not_enum(self):
        """Node must write a plain str to state, not a ChatIntent enum."""
        state = {"message": "How much water did I drink?"}
        result = classify_intent_node(state)
        assert isinstance(result["intent"], str)


# ── gather_context_node ───────────────────────────────────────────────────────

class TestGatherContextNode:
    """gather_context_node is tested by patching gather_context at the
    import site inside habittracker.graph.nodes.

    Session is now injected via config["configurable"]["session"] rather
    than state["session"] (MemorySaver cannot serialise a Session).
    """

    def _make_state(self, intent: ChatIntent = ChatIntent.BOTTLE_ACTIVITY):
        return {
            "user_id": uuid.uuid4(),
            "intent": str(intent),
            "message": "How much water did I drink today?",
        }

    def _config(self):
        return {"configurable": {"session": MagicMock()}}

    def test_populates_evidence_and_context(self, monkeypatch):
        mock_context = ChatContextResult(
            evidence=[EvidenceItem(type="metric", label="Pickups", value="6")],
            context_text="Bottle pickups today: 6",
            used_notes=False,
        )
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: mock_context,
        )
        mock_embed = MagicMock()
        node = make_gather_context_node(mock_embed)
        result = node(self._make_state(), self._config())

        assert result["evidence"] == mock_context.evidence
        assert result["context_text"] == "Bottle pickups today: 6"
        assert result["used_notes"] is False

    def test_used_notes_true_for_note_pattern(self, monkeypatch):
        mock_context = ChatContextResult(
            evidence=[EvidenceItem(type="note", label="2026-03-20", value="Felt tired")],
            context_text="Note: Felt tired",
            used_notes=True,
        )
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: mock_context,
        )
        mock_embed = MagicMock()
        node = make_gather_context_node(mock_embed)
        result = node(self._make_state(ChatIntent.NOTE_PATTERN), self._config())

        assert result["used_notes"] is True

    def test_passes_correct_intent_to_gather_context(self, monkeypatch):
        """Node must convert state["intent"] string back to ChatIntent enum."""
        captured = {}

        def fake_gather(session, user_id, intent, message, embed_provider):
            captured["intent"] = intent
            return ChatContextResult(evidence=[], context_text="", used_notes=False)

        monkeypatch.setattr("habittracker.graph.nodes.gather_context", fake_gather)
        mock_embed = MagicMock()
        node = make_gather_context_node(mock_embed)
        node(self._make_state(ChatIntent.HABIT_SUMMARY), self._config())

        assert captured["intent"] == ChatIntent.HABIT_SUMMARY

    def test_empty_evidence_on_no_data(self, monkeypatch):
        mock_context = ChatContextResult(evidence=[], context_text="", used_notes=False)
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: mock_context,
        )
        node = make_gather_context_node(MagicMock())
        result = node(self._make_state(), self._config())

        assert result["evidence"] == []
        assert result["context_text"] == ""


# ── generate_answer_node ──────────────────────────────────────────────────────

class TestGenerateAnswerNode:
    def _evidence(self):
        return [EvidenceItem(type="metric", label="Pickups", value="6")]

    def test_fallback_on_empty_evidence(self):
        mock_chat = MagicMock()
        node = make_generate_answer_node(mock_chat)
        state = {"evidence": [], "context_text": "", "message": "How much water?"}
        result = node(state)

        assert result["answer"] == FALLBACK_ANSWER
        mock_chat.complete.assert_not_called()

    def test_fallback_when_evidence_key_missing(self):
        """evidence key absent from state (UNSUPPORTED path)."""
        mock_chat = MagicMock()
        node = make_generate_answer_node(mock_chat)
        state = {"context_text": "", "message": "hello"}
        result = node(state)

        assert result["answer"] == FALLBACK_ANSWER
        mock_chat.complete.assert_not_called()

    def test_calls_llm_with_evidence(self):
        mock_chat = MagicMock()
        mock_chat.complete.return_value = "You drank 6 times today."
        node = make_generate_answer_node(mock_chat)
        state = {
            "evidence": self._evidence(),
            "context_text": "Bottle pickups today: 6",
            "message": "How much water did I drink?",
        }
        result = node(state)

        assert result["answer"] == "You drank 6 times today."
        mock_chat.complete.assert_called_once()

    def test_prompt_contains_context_and_message(self):
        """The user prompt passed to the LLM must include both data and question."""
        mock_chat = MagicMock()
        mock_chat.complete.return_value = "Answer."
        node = make_generate_answer_node(mock_chat)
        state = {
            "evidence": self._evidence(),
            "context_text": "Bottle pickups: 6",
            "message": "How much water?",
        }
        node(state)

        _, user_prompt = mock_chat.complete.call_args[0]
        assert "Bottle pickups: 6" in user_prompt
        assert "How much water?" in user_prompt

    def test_answer_truncated_at_max_len(self):
        long_answer = "x" * (MAX_ANSWER_LEN + 100)
        mock_chat = MagicMock()
        mock_chat.complete.return_value = long_answer
        node = make_generate_answer_node(mock_chat)
        state = {
            "evidence": self._evidence(),
            "context_text": "Some context",
            "message": "Tell me everything",
        }
        result = node(state)

        assert len(result["answer"]) == MAX_ANSWER_LEN

    def test_answer_not_truncated_when_within_limit(self):
        short_answer = "You drank 6 times."
        mock_chat = MagicMock()
        mock_chat.complete.return_value = short_answer
        node = make_generate_answer_node(mock_chat)
        state = {
            "evidence": self._evidence(),
            "context_text": "Pickups: 6",
            "message": "Water?",
        }
        result = node(state)

        assert result["answer"] == short_answer


# ── builder smoke test ────────────────────────────────────────────────────────

class TestBuildChatGraph:
    """Verify the graph compiles without errors."""

    def test_graph_compiles(self):
        from habittracker.graph.builder import build_chat_graph

        mock_embed = MagicMock()
        mock_chat = MagicMock()
        graph = build_chat_graph(mock_embed, mock_chat)
        # A compiled graph exposes .invoke() and .get_graph()
        assert callable(graph.invoke)

    def test_graph_has_expected_nodes(self):
        from habittracker.graph.builder import build_chat_graph

        graph = build_chat_graph(MagicMock(), MagicMock())
        node_names = set(graph.get_graph().nodes.keys())
        assert "classify_intent" in node_names
        assert "gather_context" in node_names
        assert "generate_answer" in node_names
