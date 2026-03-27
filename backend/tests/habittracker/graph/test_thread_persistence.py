"""Thread persistence tests for the LangGraph chat pipeline — phase-06-rev04.

Tests that a graph compiled with MemorySaver:
  - Accepts config={"configurable": {"thread_id": "..."}} on graph.invoke()
  - Returns valid results across multiple sequential invocations on the
    same thread_id
  - Maintains a checkpoint that can be inspected via graph.get_state()

All tests use a fresh MemorySaver per test so checkpoint state never
leaks across test cases.
"""

import uuid
from unittest.mock import MagicMock

import pytest

from langgraph.checkpoint.memory import MemorySaver

from habittracker.graph.builder import build_chat_graph
from habittracker.schemas.chat import EvidenceItem
from habittracker.schemas.intent import ChatIntent
from habittracker.services.chat_context_service import ChatContextResult
from habittracker.services.chat_service import FALLBACK_ANSWER


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def mock_chat():
    provider = MagicMock()
    provider.complete.return_value = "You drank 6 times today."
    return provider


@pytest.fixture()
def graph_with_memory(mock_chat):
    """Graph compiled with a fresh MemorySaver for each test."""
    return build_chat_graph(MagicMock(), mock_chat, checkpointer=MemorySaver())


def _state(message: str) -> dict:
    return {
        "user_id": uuid.uuid4(),
        "session": None,   # None is msgpack-serializable; gather_context is
                           # always monkeypatched in these tests so session is
                           # never actually used by a node.
        "message": message,
        "thread_id": str(uuid.uuid4()),
    }


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _bottle_context() -> ChatContextResult:
    return ChatContextResult(
        evidence=[EvidenceItem(type="metric", label="Pickups", value="6")],
        context_text="Bottle pickups: 6",
        used_notes=False,
    )


# ── Single invocation with checkpointer ──────────────────────────────────────

class TestSingleInvocationWithMemorySaver:

    def test_invoke_with_thread_id_config_succeeds(
        self, graph_with_memory, monkeypatch
    ):
        """graph.invoke() with a MemorySaver must accept a thread_id config."""
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )
        thread_id = str(uuid.uuid4())
        state = _state("How much water did I drink?")
        result = graph_with_memory.invoke(state, config=_config(thread_id))

        assert result["intent"] == "bottle_activity"
        assert result["answer"] == "You drank 6 times today."

    def test_invoke_unsupported_with_checkpointer(self, graph_with_memory):
        """UNSUPPORTED intent works correctly through a checkpointed graph."""
        state = _state("hello")
        thread_id = str(uuid.uuid4())
        result = graph_with_memory.invoke(state, config=_config(thread_id))

        assert result["intent"] == "unsupported"
        assert result["answer"] == FALLBACK_ANSWER

    def test_checkpoint_saved_after_invocation(
        self, graph_with_memory, monkeypatch
    ):
        """After invoke(), get_state() returns the saved checkpoint."""
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )
        thread_id = str(uuid.uuid4())
        state = _state("How much water did I drink?")
        graph_with_memory.invoke(state, config=_config(thread_id))

        saved = graph_with_memory.get_state(_config(thread_id))
        # StateSnapshot.values holds the last state dict
        assert saved.values["intent"] == "bottle_activity"
        assert saved.values["answer"] == "You drank 6 times today."


# ── Two sequential invocations on the same thread_id ─────────────────────────

class TestThreadPersistence:

    def test_two_invocations_same_thread_both_succeed(
        self, graph_with_memory, mock_chat, monkeypatch
    ):
        """Two sequential graph.invoke() calls on the same thread_id return
        valid results for different messages."""
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )
        thread_id = str(uuid.uuid4())

        # Turn 1
        state1 = _state("How much water did I drink?")
        result1 = graph_with_memory.invoke(state1, config=_config(thread_id))
        assert result1["intent"] == "bottle_activity"

        # Turn 2 — same thread, different question
        mock_chat.complete.return_value = "Your morning run is on track."
        state2 = _state("Did I complete my morning habit?")
        result2 = graph_with_memory.invoke(state2, config=_config(thread_id))
        assert result2["intent"] == "habit_summary"

    def test_two_threads_are_isolated(
        self, graph_with_memory, mock_chat, monkeypatch
    ):
        """Different thread_ids must not share checkpoint state."""
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )
        thread_a = str(uuid.uuid4())
        thread_b = str(uuid.uuid4())

        graph_with_memory.invoke(_state("How much water?"), config=_config(thread_a))
        mock_chat.complete.return_value = "Different answer."
        graph_with_memory.invoke(_state("How much water?"), config=_config(thread_b))

        state_a = graph_with_memory.get_state(_config(thread_a))
        state_b = graph_with_memory.get_state(_config(thread_b))

        # Each thread saved its own checkpoint independently
        assert state_a.values["answer"] == "You drank 6 times today."
        assert state_b.values["answer"] == "Different answer."

    def test_checkpoint_history_grows_with_invocations(
        self, graph_with_memory, monkeypatch
    ):
        """get_state_history() should have entries after multiple invocations."""
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )
        thread_id = str(uuid.uuid4())

        graph_with_memory.invoke(_state("How much water?"), config=_config(thread_id))
        graph_with_memory.invoke(_state("Did I complete my habit?"), config=_config(thread_id))

        history = list(graph_with_memory.get_state_history(_config(thread_id)))
        assert len(history) >= 2


# ── Schema fields ─────────────────────────────────────────────────────────────

class TestChatRequestSchema:
    """Verify thread_id was added to ChatRequest correctly."""

    def test_thread_id_defaults_to_none(self):
        from habittracker.schemas.chat import ChatRequest
        req = ChatRequest(message="How much water did I drink?")
        assert req.thread_id is None

    def test_thread_id_accepted_when_provided(self):
        from habittracker.schemas.chat import ChatRequest
        req = ChatRequest(message="How much water?", thread_id="abc-123")
        assert req.thread_id == "abc-123"


class TestChatResponseSchema:
    """Verify thread_id was added to ChatResponse correctly."""

    def test_thread_id_defaults_to_none(self):
        from habittracker.schemas.chat import ChatResponse, EvidenceItem
        resp = ChatResponse(
            answer="ok", intent="general_question",
            used_notes=False, evidence=[],
        )
        assert resp.thread_id is None

    def test_thread_id_populated_when_set(self):
        from habittracker.schemas.chat import ChatResponse
        resp = ChatResponse(
            answer="ok", intent="general_question",
            used_notes=False, evidence=[], thread_id="abc-123",
        )
        assert resp.thread_id == "abc-123"

    def test_thread_id_in_serialised_json(self):
        from habittracker.schemas.chat import ChatResponse
        resp = ChatResponse(
            answer="ok", intent="general_question",
            used_notes=False, evidence=[], thread_id="abc-123",
        )
        assert resp.model_dump()["thread_id"] == "abc-123"
