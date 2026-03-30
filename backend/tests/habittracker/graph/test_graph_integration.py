"""End-to-end integration tests for the LangGraph chat pipeline.

These tests run the full graph (classify → route → gather → generate) using
`graph.invoke()`.  The DB and LLM are replaced with mocks so no external
services are required.

Mock boundary:
  - `habittracker.graph.nodes.gather_context` is monkeypatched so the
    graph can run without a real database session.
  - `chat_provider.complete` is a MagicMock — no Ollama needed.
  - `embed_provider` is a MagicMock — never actually called by these tests
    (gather_context is patched before it would be reached).

Intent paths covered:
  BOTTLE_ACTIVITY  → gather_context → generate_answer (LLM path)
  HABIT_SUMMARY    → gather_context → generate_answer (LLM path)
  NOTE_PATTERN     → gather_context → generate_answer (used_notes=True)
  GENERAL          → gather_context → generate_answer (LLM path)
  UNSUPPORTED      → generate_answer (fallback, no context, LLM not called)

Edge cases covered:
  - supported intent + empty evidence  → fallback, no LLM call
  - answer length cap (> MAX_ANSWER_LEN chars)
  - state fields mapped to ChatResponse contract
"""

import uuid
from unittest.mock import MagicMock

import pytest

from habittracker.graph.builder import build_chat_graph
from habittracker.schemas.chat import EvidenceItem
from habittracker.schemas.intent import ChatIntent
from habittracker.services.chat_context_service import ChatContextResult
from habittracker.services.chat_service import FALLBACK_ANSWER, MAX_ANSWER_LEN


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture()
def mock_embed():
    return MagicMock()


@pytest.fixture()
def mock_chat():
    provider = MagicMock()
    provider.complete.return_value = "You drank 6 times today, totalling 1800 ml."
    return provider


@pytest.fixture()
def graph(mock_embed, mock_chat):
    return build_chat_graph(mock_embed, mock_chat)


def _base_state(message: str) -> dict:
    """Minimal input state for graph.invoke(). Session is passed via config."""
    return {
        "user_id": uuid.uuid4(),
        "message": message,
        "thread_id": str(uuid.uuid4()),
    }


def _config() -> dict:
    """Config dict with a mock session injected for gather_context_node."""
    return {"configurable": {"session": MagicMock()}}


def _bottle_context() -> ChatContextResult:
    return ChatContextResult(
        evidence=[
            EvidenceItem(type="metric", label="Bottle pickups today", value="6"),
            EvidenceItem(type="metric", label="Total hydration", value="1800 ml"),
        ],
        context_text="Bottle pickups today: 6\nTotal hydration: 1800 ml",
        used_notes=False,
    )


def _note_context() -> ChatContextResult:
    return ChatContextResult(
        evidence=[
            EvidenceItem(type="note", label="2026-03-20", value="Felt tired all day"),
        ],
        context_text="Note (2026-03-20): Felt tired all day",
        used_notes=True,
    )


# ── Happy-path intent tests ───────────────────────────────────────────────────

class TestGraphHappyPath:

    def test_bottle_activity_end_to_end(self, graph, mock_chat, monkeypatch):
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )
        state = graph.invoke(_base_state("How much water did I drink today?"), config=_config())

        assert state["intent"] == "bottle_activity"
        assert len(state["evidence"]) == 2
        assert state["used_notes"] is False
        assert state["answer"] == "You drank 6 times today, totalling 1800 ml."
        mock_chat.complete.assert_called_once()

    def test_habit_summary_end_to_end(self, graph, mock_chat, monkeypatch):
        habit_context = ChatContextResult(
            evidence=[EvidenceItem(type="habit", label="Morning run", value="completed")],
            context_text="Morning run: completed",
            used_notes=False,
        )
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: habit_context,
        )
        state = graph.invoke(_base_state("Did I complete my morning habit today?"), config=_config())

        assert state["intent"] == "habit_summary"
        assert state["used_notes"] is False
        assert state["answer"] == mock_chat.complete.return_value

    def test_note_pattern_sets_used_notes_true(self, graph, mock_chat, monkeypatch):
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _note_context(),
        )
        state = graph.invoke(_base_state("Why do I always feel tired?"), config=_config())

        assert state["intent"] == "note_pattern_question"
        assert state["used_notes"] is True
        assert state["evidence"][0].type == "note"

    def test_general_question_end_to_end(self, graph, mock_chat, monkeypatch):
        general_context = ChatContextResult(
            evidence=[EvidenceItem(type="metric", label="Active habits", value="3")],
            context_text="Active habits: 3",
            used_notes=False,
        )
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: general_context,
        )
        state = graph.invoke(_base_state("Give me a summary of my progress"), config=_config())

        assert state["intent"] == "general_question"
        assert len(state["evidence"]) > 0


# ── UNSUPPORTED shortcut ──────────────────────────────────────────────────────

class TestGraphUnsupportedShortcut:

    def test_unsupported_returns_fallback(self, graph, mock_chat, monkeypatch):
        """gather_context must never be called for UNSUPPORTED intent."""
        gather_called = []
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: gather_called.append(True) or ChatContextResult(),
        )
        state = graph.invoke(_base_state("hello"), config=_config())

        assert state["intent"] == "unsupported"
        assert state["answer"] == FALLBACK_ANSWER
        assert gather_called == []        # routing skipped gather_context_node
        mock_chat.complete.assert_not_called()

    def test_unsupported_short_message(self, graph, mock_chat):
        state = graph.invoke(_base_state("hi"), config=_config())

        assert state["intent"] == "unsupported"
        assert state["answer"] == FALLBACK_ANSWER
        mock_chat.complete.assert_not_called()


# ── No-evidence fallback (supported intent, empty data) ──────────────────────

class TestGraphNoEvidenceFallback:

    def test_supported_intent_empty_evidence_returns_fallback(
        self, graph, mock_chat, monkeypatch
    ):
        """When gather_context returns empty evidence the LLM is never called."""
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: ChatContextResult(evidence=[], context_text="", used_notes=False),
        )
        state = graph.invoke(_base_state("How much water did I drink today?"), config=_config())

        assert state["answer"] == FALLBACK_ANSWER
        mock_chat.complete.assert_not_called()

    def test_used_notes_false_when_no_evidence(self, graph, monkeypatch):
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: ChatContextResult(evidence=[], context_text="", used_notes=False),
        )
        state = graph.invoke(_base_state("How much water did I drink?"), config=_config())

        assert state["used_notes"] is False


# ── Answer length cap ─────────────────────────────────────────────────────────

class TestGraphAnswerCap:

    def test_answer_truncated_to_max_len(self, graph, mock_chat, monkeypatch):
        mock_chat.complete.return_value = "x" * (MAX_ANSWER_LEN + 200)
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )
        state = graph.invoke(_base_state("How much water did I drink?"), config=_config())

        assert len(state["answer"]) == MAX_ANSWER_LEN

    def test_answer_not_truncated_when_within_limit(self, graph, mock_chat, monkeypatch):
        short = "You drank 6 times."
        mock_chat.complete.return_value = short
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )
        state = graph.invoke(_base_state("How much water?"), config=_config())

        assert state["answer"] == short


# ── ChatResponse contract mapping ─────────────────────────────────────────────

class TestGraphResponseContract:
    """Verify that the final state contains exactly the fields
    the endpoint maps to ChatResponse (answer, intent, used_notes, evidence).
    """

    def test_all_response_fields_present(self, graph, mock_chat, monkeypatch):
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )
        state = graph.invoke(_base_state("How much water did I drink?"), config=_config())

        assert "answer" in state
        assert "intent" in state
        assert "used_notes" in state
        assert "evidence" in state

    def test_evidence_items_are_evidence_item_instances(self, graph, mock_chat, monkeypatch):
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )
        state = graph.invoke(_base_state("How much water did I drink?"), config=_config())

        for item in state["evidence"]:
            assert isinstance(item, EvidenceItem)

    def test_intent_is_string(self, graph, monkeypatch, mock_chat):
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )
        state = graph.invoke(_base_state("How much water did I drink?"), config=_config())

        assert isinstance(state["intent"], str)

    def test_output_matches_handle_chat_shape(self, graph, mock_chat, monkeypatch):
        """State fields align with what handle_chat returns in ChatResponse."""
        from habittracker.schemas.chat import ChatResponse

        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )
        state = graph.invoke(_base_state("How much water did I drink?"), config=_config())

        # Build a ChatResponse from graph state — must not raise
        response = ChatResponse(
            answer=state["answer"],
            intent=state["intent"],
            used_notes=state["used_notes"],
            evidence=state["evidence"],
        )
        assert response.answer == state["answer"]
        assert response.intent == "bottle_activity"
