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
  - For SQL_ANALYTICS tests, `sql_pipeline_service.run` is monkeypatched
    so no real DB or LLM is needed.

Intent paths covered:
  BOTTLE_ACTIVITY  → gather_context → generate_answer (LLM path)
  HABIT_SUMMARY    → gather_context → generate_answer (LLM path)
  NOTE_PATTERN     → gather_context → generate_answer (used_notes=True)
  GENERAL          → gather_context → generate_answer (LLM path)
  UNSUPPORTED      → generate_answer (fallback, no context, LLM not called)
  SQL_ANALYTICS    → sql_analytics  → END (pipeline, gather_context NOT called)

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
from habittracker.schemas.sql_chat import (
    SqlExecutionResult,
    SqlPipelineResult,
    SqlValidationResult,
    ValidationStatus,
)
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
        "current_message": message,
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


# ── SQL_ANALYTICS path ────────────────────────────────────────────────────────

def _sql_success_result(answer: str = "Your best day was Monday with 8 completions.") -> SqlPipelineResult:
    """A fully successful SqlPipelineResult with one row of data."""
    execution = SqlExecutionResult(
        columns=["day", "count"],
        rows=[{"day": "Monday", "count": 8}],
        row_count=1,
        sql="SELECT day, count FROM habits WHERE user_id = :user_id LIMIT 10",
    )
    return SqlPipelineResult(
        question="Which day had the highest completions?",
        generated_sql="SELECT day, count FROM habits WHERE user_id = :user_id LIMIT 10",
        validation=SqlValidationResult(
            status=ValidationStatus.OK,
            sql="SELECT day, count FROM habits WHERE user_id = :user_id LIMIT 10",
        ),
        execution=execution,
        success=True,
        answer=answer,
    )


def _sql_failure_result(reason: str = "SQL generation failed: unsupported question") -> SqlPipelineResult:
    """A failed SqlPipelineResult (generation failure)."""
    return SqlPipelineResult(
        question="Which day had the highest completions?",
        generated_sql="",
        validation=SqlValidationResult(
            status=ValidationStatus.REJECTED,
            sql="",
            rejection_reason="SQL generation failed before validation.",
        ),
        execution=None,
        success=False,
        failure_reason=reason,
    )


@pytest.fixture()
def mock_pipeline():
    svc = MagicMock()
    svc.run.return_value = _sql_success_result()
    return svc


@pytest.fixture()
def sql_graph(mock_embed, mock_chat, mock_pipeline, monkeypatch):
    """Graph built after patching sql_pipeline_service so the sql_analytics_node
    closure captures the mock rather than the real singleton."""
    monkeypatch.setattr("habittracker.graph.builder.sql_pipeline_service", mock_pipeline)
    return build_chat_graph(mock_embed, mock_chat)


class TestGraphSqlAnalyticsPath:
    """Verify that SQL_ANALYTICS intent routes to sql_analytics_node and NOT
    to gather_context_node, and that the answer comes from the SQL pipeline.

    Uses the sql_graph fixture so the mock pipeline is baked into the graph
    closure at build time (monkeypatching after build doesn't reach closures).
    """

    def test_sql_question_routes_to_sql_analytics(self, sql_graph, mock_chat, mock_pipeline, monkeypatch):
        """A question with SQL analytics keywords must hit the sql_analytics node,
        not gather_context."""
        gather_called = []
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: gather_called.append(True) or ChatContextResult(),
        )

        state = sql_graph.invoke(
            _base_state("Which day had the highest completions?"),
            config=_config(),
        )

        assert state["intent"] == "sql_analytics"
        assert gather_called == []              # gather_context was never called
        mock_chat.complete.assert_not_called()  # chat LLM was never called

    def test_sql_answer_comes_from_pipeline(self, sql_graph, mock_pipeline):
        """The answer written to state must be the one returned by the pipeline,
        not generated by the chat LLM."""
        mock_pipeline.run.return_value = _sql_success_result("Monday was your best day.")

        state = sql_graph.invoke(
            _base_state("Which day had the highest completions?"),
            config=_config(),
        )

        assert state["answer"] == "Monday was your best day."

    def test_sql_result_stored_in_state(self, sql_graph, mock_pipeline):
        """sql_pipeline_result must be written to state for downstream use."""
        pipeline_result = _sql_success_result()
        mock_pipeline.run.return_value = pipeline_result

        state = sql_graph.invoke(
            _base_state("Which day had the highest completions?"),
            config=_config(),
        )

        assert state["sql_pipeline_result"] is pipeline_result
        assert state["sql_pipeline_result"].success is True

    def test_sql_evidence_built_from_rows(self, sql_graph, mock_pipeline):
        """Evidence items must be built from the SQL execution rows."""
        state = sql_graph.invoke(
            _base_state("Which day had the highest completions?"),
            config=_config(),
        )

        assert len(state["evidence"]) > 0
        assert all(item.type == "sql_result" for item in state["evidence"])

    def test_sql_used_notes_is_false(self, sql_graph, mock_pipeline):
        """SQL analytics answers never use note search."""
        state = sql_graph.invoke(
            _base_state("Which day had the highest completions?"),
            config=_config(),
        )

        assert state["used_notes"] is False

    def test_sql_pipeline_failure_returns_safe_answer(self, sql_graph, mock_pipeline):
        """When the pipeline fails, a human-readable fallback is returned — not an exception."""
        mock_pipeline.run.return_value = _sql_failure_result("SQL generation failed: unsupported")

        state = sql_graph.invoke(
            _base_state("Which day had the highest completions?"),
            config=_config(),
        )

        assert state["intent"] == "sql_analytics"
        assert state["sql_pipeline_result"].success is False
        assert "SQL generation failed" in state["answer"]

    def test_bottle_question_does_not_hit_sql(self, sql_graph, mock_pipeline, mock_chat, monkeypatch):
        """A question with bottle keywords must hit gather_context, NOT sql_analytics."""
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )

        state = sql_graph.invoke(
            _base_state("How much water did I drink today?"),
            config=_config(),
        )

        assert state["intent"] == "bottle_activity"
        mock_pipeline.run.assert_not_called()   # sql_analytics_node was never called

    def test_habit_question_does_not_hit_sql(self, sql_graph, mock_pipeline, mock_chat, monkeypatch):
        """A question with habit keywords must hit gather_context, NOT sql_analytics."""
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: ChatContextResult(
                evidence=[EvidenceItem(type="habit", label="Run", value="done")],
                context_text="Run: done",
                used_notes=False,
            ),
        )

        state = sql_graph.invoke(
            _base_state("Did I complete my morning habit today?"),
            config=_config(),
        )

        assert state["intent"] == "habit_summary"
        mock_pipeline.run.assert_not_called()

    @pytest.mark.parametrize("message,expected_intent", [
        ("Which day had the highest completions?",                                "sql_analytics"),
        ("What is my average completion per week?",                               "sql_analytics"),
        ("Compare this week vs last week",                                        "sql_analytics"),
        ("Tell me in last 30 days average water drank per day",                   "sql_analytics"),
        ("How much water did I drink today?",                                     "bottle_activity"),
        ("Did I complete my morning habit?",                                      "habit_summary"),
        ("Why do I feel tired on Fridays?",                                       "note_pattern_question"),
        ("hello",                                                                 "unsupported"),
    ])
    def test_intent_routing_matrix(self, sql_graph, mock_pipeline, mock_chat, monkeypatch, message, expected_intent):
        """Parametrized smoke test — verify each message hits the expected intent,
        proving that SQL questions route to sql_analytics and others do not."""
        monkeypatch.setattr(
            "habittracker.graph.nodes.gather_context",
            lambda *a, **k: _bottle_context(),
        )

        state = sql_graph.invoke(_base_state(message), config=_config())

        assert state["intent"] == expected_intent
