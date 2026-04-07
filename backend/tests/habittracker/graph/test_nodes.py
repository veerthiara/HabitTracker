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
        state = {"current_message": "How much water did I drink today?"}
        result = classify_intent_node(state)
        assert result["intent"] == "bottle_activity"

    def test_habit_message(self):
        state = {"current_message": "Did I complete my morning habit?"}
        result = classify_intent_node(state)
        assert result["intent"] == "habit_summary"

    def test_note_pattern_message(self):
        # "habit" is checked before "why" in the classifier, so the message
        # must not contain habit keywords to reach NOTE_PATTERN.
        state = {"current_message": "Why do I always feel tired on Fridays?"}
        result = classify_intent_node(state)
        assert result["intent"] == "note_pattern_question"

    def test_general_message(self):
        state = {"current_message": "Give me a summary of my week"}
        result = classify_intent_node(state)
        assert result["intent"] == "general_question"

    def test_unsupported_greeting(self):
        state = {"current_message": "hello"}
        result = classify_intent_node(state)
        assert result["intent"] == "unsupported"

    def test_returns_string_not_enum(self):
        """Node must write a plain str to state, not a ChatIntent enum."""
        state = {"current_message": "How much water did I drink?"}
        result = classify_intent_node(state)
        assert isinstance(result["intent"], str)

    def test_does_not_write_messages(self):
        """classify_intent_node must NOT touch messages — generate_answer_node
        is the sole writer of conversation history."""
        state = {"current_message": "How much water did I drink today?"}
        result = classify_intent_node(state)
        assert "messages" not in result


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
            "current_message": "How much water did I drink today?",
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

    def _state_with_evidence(self, prior_messages=None):
        """State for a turn. messages contains only completed prior pairs;
        current_message is the fresh user input for this turn."""
        return {
            "evidence": self._evidence(),
            "context_text": "Bottle pickups today: 6",
            "current_message": "How much water did I drink?",
            "messages": list(prior_messages or []),
        }

    def test_fallback_on_empty_evidence(self):
        mock_chat = MagicMock()
        node = make_generate_answer_node(mock_chat)
        state = {"evidence": [], "context_text": "", "current_message": "How much water?", "messages": []}
        result = node(state)

        assert result["answer"] == FALLBACK_ANSWER
        mock_chat.complete.assert_not_called()

    def test_fallback_appends_both_turns(self):
        """On fallback, generate_answer_node appends the user turn AND the
        fallback assistant reply so the thread history stays complete."""
        mock_chat = MagicMock()
        node = make_generate_answer_node(mock_chat)
        state = {"evidence": [], "context_text": "", "current_message": "hello", "messages": []}
        result = node(state)

        assert len(result["messages"]) == 2
        assert result["messages"][0] == {"role": "user", "content": "hello"}
        assert result["messages"][1] == {"role": "assistant", "content": FALLBACK_ANSWER}

    def test_fallback_when_evidence_key_missing(self):
        """evidence key absent from state (UNSUPPORTED path)."""
        mock_chat = MagicMock()
        node = make_generate_answer_node(mock_chat)
        state = {"context_text": "", "current_message": "hello"}
        result = node(state)

        assert result["answer"] == FALLBACK_ANSWER
        mock_chat.complete.assert_not_called()

    def test_calls_llm_with_evidence(self):
        mock_chat = MagicMock()
        mock_chat.complete.return_value = "You drank 6 times today."
        node = make_generate_answer_node(mock_chat)
        result = node(self._state_with_evidence())

        assert result["answer"] == "You drank 6 times today."
        mock_chat.complete.assert_called_once()

    def test_llm_receives_message_list(self):
        """complete() must be called with a list of dicts (not two strings)."""
        mock_chat = MagicMock()
        mock_chat.complete.return_value = "Answer."
        node = make_generate_answer_node(mock_chat)
        node(self._state_with_evidence())

        args, _ = mock_chat.complete.call_args
        assert len(args) == 1
        assert isinstance(args[0], list)
        assert all("role" in m and "content" in m for m in args[0])

    def test_prompt_contains_evidence_context(self):
        """The current user turn content must include the DB evidence text."""
        mock_chat = MagicMock()
        mock_chat.complete.return_value = "Answer."
        node = make_generate_answer_node(mock_chat)
        node(self._state_with_evidence())

        messages = mock_chat.complete.call_args[0][0]
        last_user = next(m for m in reversed(messages) if m["role"] == "user")
        assert "Bottle pickups today: 6" in last_user["content"]
        assert "How much water did I drink?" in last_user["content"]

    def test_system_prompt_is_first_message(self):
        mock_chat = MagicMock()
        mock_chat.complete.return_value = "Answer."
        node = make_generate_answer_node(mock_chat)
        node(self._state_with_evidence())

        messages = mock_chat.complete.call_args[0][0]
        assert messages[0]["role"] == "system"

    def test_prior_history_included_in_payload(self):
        """Prior completed pairs are sent verbatim in the LLM payload."""
        mock_chat = MagicMock()
        mock_chat.complete.return_value = "Answer."
        node = make_generate_answer_node(mock_chat)
        prior = [
            {"role": "user", "content": "I drank 8 glasses"},
            {"role": "assistant", "content": "Got it!"},
        ]
        node(self._state_with_evidence(prior_messages=prior))

        messages = mock_chat.complete.call_args[0][0]
        # system + 2 prior + current user = 4
        assert len(messages) == 4
        assert messages[1] == {"role": "user", "content": "I drank 8 glasses"}
        assert messages[2] == {"role": "assistant", "content": "Got it!"}

    def test_history_trust_rules_in_system_prompt(self):
        """Trust-level rules must live in the system prompt, not the user turn.
        The system prompt must distinguish verified evidence from session history."""
        mock_chat = MagicMock()
        mock_chat.complete.return_value = "Answer."
        node = make_generate_answer_node(mock_chat)
        prior = [
            {"role": "user", "content": "I drank 8 glasses"},
            {"role": "assistant", "content": "Noted!"},
        ]
        node(self._state_with_evidence(prior_messages=prior))

        messages = mock_chat.complete.call_args[0][0]
        system_content = messages[0]["content"]   # layer 1
        assert "unverified" in system_content.lower() or "session" in system_content.lower()

    def test_evidence_labeled_as_verified(self):
        """The final user content must label the DB evidence as verified."""
        mock_chat = MagicMock()
        mock_chat.complete.return_value = "Answer."
        node = make_generate_answer_node(mock_chat)
        node(self._state_with_evidence())

        messages = mock_chat.complete.call_args[0][0]
        last_user = next(m for m in reversed(messages) if m["role"] == "user")
        assert "verified" in last_user["content"].lower()

    def test_appends_both_user_and_assistant_turns(self):
        """generate_answer_node appends both the user turn and the assistant
        reply as a completed pair — messages is always even-length."""
        mock_chat = MagicMock()
        mock_chat.complete.return_value = "You drank 6 times."
        node = make_generate_answer_node(mock_chat)
        result = node(self._state_with_evidence())

        assert len(result["messages"]) == 2
        assert result["messages"][0] == {"role": "user", "content": "How much water did I drink?"}
        assert result["messages"][1] == {"role": "assistant", "content": "You drank 6 times."}

    def test_window_cap_limits_prior_turns_sent_to_llm(self):
        """Prior turns beyond CONVERSATION_WINDOW are excluded from the payload."""
        from habittracker.core.config import CONVERSATION_WINDOW
        mock_chat = MagicMock()
        mock_chat.complete.return_value = "Answer."
        node = make_generate_answer_node(mock_chat)

        many_prior = []
        for i in range(CONVERSATION_WINDOW + 4):
            many_prior.append({"role": "user", "content": f"msg {i}"})
            many_prior.append({"role": "assistant", "content": f"reply {i}"})

        node(self._state_with_evidence(prior_messages=many_prior))

        messages = mock_chat.complete.call_args[0][0]
        # system + windowed prior + current user
        prior_in_payload = [m for m in messages if m["role"] != "system"][:-1]
        assert len(prior_in_payload) <= CONVERSATION_WINDOW

    def test_answer_truncated_at_max_len(self):
        long_answer = "x" * (MAX_ANSWER_LEN + 100)
        mock_chat = MagicMock()
        mock_chat.complete.return_value = long_answer
        node = make_generate_answer_node(mock_chat)
        result = node(self._state_with_evidence())

        assert len(result["answer"]) == MAX_ANSWER_LEN

    def test_answer_not_truncated_when_within_limit(self):
        short_answer = "You drank 6 times."
        mock_chat = MagicMock()
        mock_chat.complete.return_value = short_answer
        node = make_generate_answer_node(mock_chat)
        result = node(self._state_with_evidence())

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
