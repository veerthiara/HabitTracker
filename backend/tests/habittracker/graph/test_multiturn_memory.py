"""Multi-turn conversation memory tests — phase-06-rev06.

Tests that the graph accumulates a conversation history across checkpoint turns
on the same thread_id:
  - generate_answer_node appends both user + assistant turns as a completed pair
  - messages list grows across turns (LangGraph operator.add reducer)
  - CONVERSATION_WINDOW cap: only recent turns are sent to the LLM payload
  - Conversation history is labeled as unverified in the LLM prompt
  - Evidence context is labeled as verified in the LLM prompt

All tests use MemorySaver and mock providers — no real DB or LLM required.
"""

import uuid
from unittest.mock import MagicMock

import pytest

from langgraph.checkpoint.memory import MemorySaver

from habittracker.graph.builder import build_chat_graph
from habittracker.core.config import CONVERSATION_WINDOW
from habittracker.schemas.conversation import ConversationTurn
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
def graph_mem(mock_chat):
    """Graph with MemorySaver — each test gets a fresh checkpointer."""
    return build_chat_graph(MagicMock(), mock_chat, checkpointer=MemorySaver())


def _bottle_context():
    return ChatContextResult(
        evidence=[EvidenceItem(type="metric", label="Pickups", value="6")],
        context_text="Bottle pickups: 6",
        used_notes=False,
    )


def _state(message: str) -> dict:
    return {"user_id": uuid.uuid4(), "current_message": message, "thread_id": str(uuid.uuid4())}


def _cfg(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id, "session": None}}


# ── Single-turn message accumulation ─────────────────────────────────────────

class TestMessageAccumulationSingleTurn:

    def test_user_message_in_messages_after_turn(self, graph_mem, monkeypatch):
        """classify_intent_node appends the user message to messages."""
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )
        tid = str(uuid.uuid4())
        result = graph_mem.invoke(
            {"user_id": uuid.uuid4(), "current_message": "How much water?", "thread_id": tid},
            config=_cfg(tid),
        )

        roles = [m["role"] for m in result["messages"]]
        contents = [m["content"] for m in result["messages"]]
        assert "user" in roles
        assert "How much water?" in contents

    def test_assistant_answer_in_messages_after_turn(self, graph_mem, mock_chat, monkeypatch):
        """generate_answer_node appends the assistant answer to messages."""
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )
        tid = str(uuid.uuid4())
        result = graph_mem.invoke(
            {"user_id": uuid.uuid4(), "current_message": "How much water?", "thread_id": tid},
            config=_cfg(tid),
        )

        assistant_msgs = [m for m in result["messages"] if m["role"] == "assistant"]
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0]["content"] == "You drank 6 times today."

    def test_both_user_and_assistant_appended(self, graph_mem, monkeypatch):
        """After one turn, messages must contain exactly one user + one assistant entry."""
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )
        tid = str(uuid.uuid4())
        result = graph_mem.invoke(
            {"user_id": uuid.uuid4(), "current_message": "How much water?", "thread_id": tid},
            config=_cfg(tid),
        )

        assert len(result["messages"]) == 2
        assert result["messages"][0]["role"] == "user"
        assert result["messages"][1]["role"] == "assistant"

    def test_unsupported_turn_still_appends_messages(self, graph_mem):
        """UNSUPPORTED path: user + fallback assistant messages are appended."""
        tid = str(uuid.uuid4())
        result = graph_mem.invoke(
            {"user_id": uuid.uuid4(), "current_message": "hello", "thread_id": tid},
            config=_cfg(tid),
        )

        assert len(result["messages"]) == 2
        assert result["messages"][0]["role"] == "user"
        assert result["messages"][1]["content"] == FALLBACK_ANSWER


# ── Multi-turn accumulation ───────────────────────────────────────────────────

class TestMessageAccumulationMultiTurn:

    def test_messages_grow_across_turns(self, graph_mem, mock_chat, monkeypatch):
        """After two turns on the same thread, messages has 4 entries (2 user + 2 assistant)."""
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )
        uid = uuid.uuid4()
        tid = str(uuid.uuid4())

        graph_mem.invoke(
            {"user_id": uid, "current_message": "How much water?", "thread_id": tid},
            config=_cfg(tid),
        )
        mock_chat.complete.return_value = "Your morning run habit is on track."
        result2 = graph_mem.invoke(
            {"user_id": uid, "current_message": "Did I complete my morning habit?", "thread_id": tid},
            config=_cfg(tid),
        )

        assert len(result2["messages"]) == 4
        assert result2["messages"][0]["role"] == "user"
        assert result2["messages"][1]["role"] == "assistant"
        assert result2["messages"][2]["role"] == "user"
        assert result2["messages"][3]["role"] == "assistant"

    def test_prior_turn_included_in_llm_payload_turn2(self, graph_mem, mock_chat, monkeypatch):
        """On turn 2, the LLM payload must include the prior user+assistant messages."""
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )
        uid = uuid.uuid4()
        tid = str(uuid.uuid4())

        # Turn 1
        graph_mem.invoke(
            {"user_id": uid, "current_message": "I drank 8 glasses of water today", "thread_id": tid},
            config=_cfg(tid),
        )

        # Turn 2 — capture what the LLM receives
        mock_chat.complete.return_value = "You told me you drank 8 glasses."
        graph_mem.invoke(
            {"user_id": uid, "current_message": "What did I just tell you?", "thread_id": tid},
            config=_cfg(tid),
        )

        # The second call is the Turn 2 LLM call
        turn2_call_args = mock_chat.complete.call_args_list[-1]
        payload = turn2_call_args[0][0]  # first positional arg = messages list
        all_content = " ".join(m["content"] for m in payload)
        assert "8 glasses" in all_content

    def test_separate_threads_do_not_share_history(self, graph_mem, mock_chat, monkeypatch):
        """Two different thread_ids must not share conversation history."""
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )
        uid = uuid.uuid4()
        tid_a = str(uuid.uuid4())
        tid_b = str(uuid.uuid4())

        graph_mem.invoke(
            {"user_id": uid, "current_message": "Thread A message", "thread_id": tid_a},
            config=_cfg(tid_a),
        )
        result_b = graph_mem.invoke(
            {"user_id": uid, "current_message": "Thread B message", "thread_id": tid_b},
            config=_cfg(tid_b),
        )

        # Thread B must not contain Thread A's message
        all_content_b = " ".join(m["content"] for m in result_b["messages"])
        assert "Thread A message" not in all_content_b


# ── Window cap ────────────────────────────────────────────────────────────────

class TestConversationWindowCap:

    def test_window_cap_enforced_in_llm_payload(self, mock_chat, monkeypatch):
        """When more turns than CONVERSATION_WINDOW exist, only the most recent
        CONVERSATION_WINDOW turns are sent to the LLM (in prior history)."""
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )
        graph = build_chat_graph(MagicMock(), mock_chat, checkpointer=MemorySaver())
        uid = uuid.uuid4()
        tid = str(uuid.uuid4())

        # Exceed the window by running more turns than CONVERSATION_WINDOW pairs
        turns_to_run = (CONVERSATION_WINDOW // 2) + 3
        for i in range(turns_to_run):
            mock_chat.complete.return_value = f"Reply {i}"
            graph.invoke(
                {"user_id": uid, "current_message": f"Question {i}", "thread_id": tid},
                config=_cfg(tid),
            )

        # The final LLM call — inspect the payload
        final_payload = mock_chat.complete.call_args_list[-1][0][0]
        non_system = [m for m in final_payload if m["role"] != "system"]
        # prior history + current user turn
        prior_in_payload = non_system[:-1]
        assert len(prior_in_payload) <= CONVERSATION_WINDOW

    def test_window_constant_is_positive_int(self):
        assert isinstance(CONVERSATION_WINDOW, int)
        assert CONVERSATION_WINDOW > 0


# ── Trust-level labeling ──────────────────────────────────────────────────────

class TestTrustLevelLabeling:

    def _run_two_turns(self, graph, mock_chat, monkeypatch):
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )
        uid = uuid.uuid4()
        tid = str(uuid.uuid4())
        graph.invoke(
            {"user_id": uid, "current_message": "I drank 8 glasses today", "thread_id": tid},
            config=_cfg(tid),
        )
        mock_chat.complete.return_value = "You told me 8 glasses."
        graph.invoke(
            {"user_id": uid, "current_message": "What did I just say?", "thread_id": tid},
            config=_cfg(tid),
        )
        return mock_chat.complete.call_args_list[-1][0][0]

    def test_evidence_labeled_verified(self, graph_mem, mock_chat, monkeypatch):
        payload = self._run_two_turns(graph_mem, mock_chat, monkeypatch)
        last_user = next(m for m in reversed(payload) if m["role"] == "user")
        assert "verified" in last_user["content"].lower()

    def test_history_trust_rules_in_system_prompt(self, graph_mem, mock_chat, monkeypatch):
        """Trust-level rules for session history must live in the system prompt."""
        payload = self._run_two_turns(graph_mem, mock_chat, monkeypatch)
        system_content = payload[0]["content"]
        assert "unverified" in system_content.lower() or "session" in system_content.lower()

    def test_system_message_is_first(self, graph_mem, mock_chat, monkeypatch):
        payload = self._run_two_turns(graph_mem, mock_chat, monkeypatch)
        assert payload[0]["role"] == "system"
