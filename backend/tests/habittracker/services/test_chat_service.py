"""Tests for chat_service.handle_chat.

Strategy:
  - Patch classify_intent and gather_context at their import path inside
    chat_service so the orchestrator logic is tested in isolation.
  - chat_provider and embed_provider are passed as MagicMock directly —
    no patching needed, they're injectable parameters.
  - Intent and context values are controlled via mock return values.

Stacked @patch decorators: bottom decorator's mock = first arg after self.
"""

import uuid
from unittest.mock import MagicMock, patch

from habittracker.providers.base import ChatCompletionError
from habittracker.schemas.chat import ChatRequest, EvidenceItem
from habittracker.schemas.intent import ChatIntent
from habittracker.services.chat_context_service import ChatContextResult
from habittracker.services.chat_service import (
    FALLBACK_ANSWER,
    MAX_ANSWER_LEN,
    SYSTEM_PROMPT,
    _build_user_prompt,
    handle_chat,
)

USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_session():
    return MagicMock()


def _make_embed_provider():
    return MagicMock()


def _make_chat_provider(answer: str = "You drank 1800 ml today."):
    provider = MagicMock()
    provider.complete.return_value = answer
    return provider


def _make_evidence():
    return [EvidenceItem(type="metric", label="Total hydration today", value="1800 ml")]


def _make_context(
    evidence=None,
    context_text="Hydration summary for 2026-03-23:\n  Total: 1800 ml",
    used_notes=False,
):
    return ChatContextResult(
        evidence=evidence if evidence is not None else _make_evidence(),
        context_text=context_text,
        used_notes=used_notes,
    )


def _make_request(message: str = "How much water did I drink?"):
    return ChatRequest(message=message)


# ── _build_user_prompt ────────────────────────────────────────────────────────


class TestBuildUserPrompt:
    def test_contains_data_label(self):
        result = _build_user_prompt("some data", "my question")
        assert "Data:" in result

    def test_contains_question_label(self):
        result = _build_user_prompt("some data", "my question")
        assert "Question:" in result

    def test_context_text_in_result(self):
        result = _build_user_prompt("hydration: 1800 ml", "question")
        assert "hydration: 1800 ml" in result

    def test_message_in_result(self):
        result = _build_user_prompt("data", "how much water?")
        assert "how much water?" in result


# ── handle_chat — happy path ──────────────────────────────────────────────────


class TestHandleChatHappyPath:
    @patch("habittracker.services.chat_service.gather_context")
    @patch("habittracker.services.chat_service.classify_intent")
    def test_returns_chat_response_with_llm_answer(self, mock_classify, mock_gather):
        mock_classify.return_value = ChatIntent.BOTTLE_ACTIVITY
        mock_gather.return_value = _make_context()
        chat_provider = _make_chat_provider("You drank 1800 ml today.")

        result = handle_chat(
            _make_session(), USER_ID, _make_request(), _make_embed_provider(), chat_provider
        )

        assert result.answer == "You drank 1800 ml today."

    @patch("habittracker.services.chat_service.gather_context")
    @patch("habittracker.services.chat_service.classify_intent")
    def test_intent_propagated_as_string_value(self, mock_classify, mock_gather):
        mock_classify.return_value = ChatIntent.BOTTLE_ACTIVITY
        mock_gather.return_value = _make_context()
        chat_provider = _make_chat_provider()

        result = handle_chat(
            _make_session(), USER_ID, _make_request(), _make_embed_provider(), chat_provider
        )

        assert result.intent == "bottle_activity"

    @patch("habittracker.services.chat_service.gather_context")
    @patch("habittracker.services.chat_service.classify_intent")
    def test_used_notes_propagated_from_context(self, mock_classify, mock_gather):
        mock_classify.return_value = ChatIntent.NOTE_PATTERN
        mock_gather.return_value = _make_context(used_notes=True)
        chat_provider = _make_chat_provider()

        result = handle_chat(
            _make_session(), USER_ID, _make_request(), _make_embed_provider(), chat_provider
        )

        assert result.used_notes is True

    @patch("habittracker.services.chat_service.gather_context")
    @patch("habittracker.services.chat_service.classify_intent")
    def test_evidence_propagated_from_context(self, mock_classify, mock_gather):
        evidence = _make_evidence()
        mock_classify.return_value = ChatIntent.BOTTLE_ACTIVITY
        mock_gather.return_value = _make_context(evidence=evidence)
        chat_provider = _make_chat_provider()

        result = handle_chat(
            _make_session(), USER_ID, _make_request(), _make_embed_provider(), chat_provider
        )

        assert result.evidence == evidence

    @patch("habittracker.services.chat_service.gather_context")
    @patch("habittracker.services.chat_service.classify_intent")
    def test_llm_called_with_system_prompt(self, mock_classify, mock_gather):
        mock_classify.return_value = ChatIntent.BOTTLE_ACTIVITY
        mock_gather.return_value = _make_context()
        chat_provider = _make_chat_provider()

        handle_chat(
            _make_session(), USER_ID, _make_request(), _make_embed_provider(), chat_provider
        )

        system_arg = chat_provider.complete.call_args[0][0]
        assert system_arg == SYSTEM_PROMPT

    @patch("habittracker.services.chat_service.gather_context")
    @patch("habittracker.services.chat_service.classify_intent")
    def test_llm_called_with_user_prompt_containing_message(self, mock_classify, mock_gather):
        mock_classify.return_value = ChatIntent.BOTTLE_ACTIVITY
        context = _make_context(context_text="Total: 1800 ml")
        mock_gather.return_value = context
        chat_provider = _make_chat_provider()
        request = _make_request("How much water?")

        handle_chat(
            _make_session(), USER_ID, request, _make_embed_provider(), chat_provider
        )

        user_arg = chat_provider.complete.call_args[0][1]
        assert "How much water?" in user_arg
        assert "Total: 1800 ml" in user_arg


# ── handle_chat — no evidence shortcut ───────────────────────────────────────


class TestHandleChatNoEvidence:
    @patch("habittracker.services.chat_service.gather_context")
    @patch("habittracker.services.chat_service.classify_intent")
    def test_empty_evidence_returns_fallback_answer(self, mock_classify, mock_gather):
        mock_classify.return_value = ChatIntent.UNSUPPORTED
        mock_gather.return_value = _make_context(evidence=[])
        chat_provider = _make_chat_provider()

        result = handle_chat(
            _make_session(), USER_ID, _make_request(), _make_embed_provider(), chat_provider
        )

        assert result.answer == FALLBACK_ANSWER

    @patch("habittracker.services.chat_service.gather_context")
    @patch("habittracker.services.chat_service.classify_intent")
    def test_empty_evidence_skips_llm_call(self, mock_classify, mock_gather):
        mock_classify.return_value = ChatIntent.UNSUPPORTED
        mock_gather.return_value = _make_context(evidence=[])
        chat_provider = _make_chat_provider()

        handle_chat(
            _make_session(), USER_ID, _make_request(), _make_embed_provider(), chat_provider
        )

        chat_provider.complete.assert_not_called()

    @patch("habittracker.services.chat_service.gather_context")
    @patch("habittracker.services.chat_service.classify_intent")
    def test_empty_evidence_returns_empty_evidence_list(self, mock_classify, mock_gather):
        mock_classify.return_value = ChatIntent.UNSUPPORTED
        mock_gather.return_value = _make_context(evidence=[])
        chat_provider = _make_chat_provider()

        result = handle_chat(
            _make_session(), USER_ID, _make_request(), _make_embed_provider(), chat_provider
        )

        assert result.evidence == []

    @patch("habittracker.services.chat_service.gather_context")
    @patch("habittracker.services.chat_service.classify_intent")
    def test_empty_evidence_used_notes_is_false(self, mock_classify, mock_gather):
        mock_classify.return_value = ChatIntent.UNSUPPORTED
        mock_gather.return_value = _make_context(evidence=[])
        chat_provider = _make_chat_provider()

        result = handle_chat(
            _make_session(), USER_ID, _make_request(), _make_embed_provider(), chat_provider
        )

        assert result.used_notes is False


# ── handle_chat — answer truncation ──────────────────────────────────────────


class TestHandleChatAnswerTruncation:
    @patch("habittracker.services.chat_service.gather_context")
    @patch("habittracker.services.chat_service.classify_intent")
    def test_long_answer_truncated_to_max_len(self, mock_classify, mock_gather):
        mock_classify.return_value = ChatIntent.GENERAL
        mock_gather.return_value = _make_context()
        long_answer = "x" * (MAX_ANSWER_LEN + 500)
        chat_provider = _make_chat_provider(answer=long_answer)

        result = handle_chat(
            _make_session(), USER_ID, _make_request(), _make_embed_provider(), chat_provider
        )

        assert len(result.answer) == MAX_ANSWER_LEN

    @patch("habittracker.services.chat_service.gather_context")
    @patch("habittracker.services.chat_service.classify_intent")
    def test_short_answer_not_truncated(self, mock_classify, mock_gather):
        mock_classify.return_value = ChatIntent.GENERAL
        mock_gather.return_value = _make_context()
        short_answer = "Great job!"
        chat_provider = _make_chat_provider(answer=short_answer)

        result = handle_chat(
            _make_session(), USER_ID, _make_request(), _make_embed_provider(), chat_provider
        )

        assert result.answer == short_answer


# ── handle_chat — error propagation ──────────────────────────────────────────


class TestHandleChatErrors:
    @patch("habittracker.services.chat_service.gather_context")
    @patch("habittracker.services.chat_service.classify_intent")
    def test_chat_completion_error_propagates(self, mock_classify, mock_gather):
        mock_classify.return_value = ChatIntent.BOTTLE_ACTIVITY
        mock_gather.return_value = _make_context()
        chat_provider = MagicMock()
        chat_provider.complete.side_effect = ChatCompletionError("Ollama down")

        try:
            handle_chat(
                _make_session(), USER_ID, _make_request(), _make_embed_provider(), chat_provider
            )
            assert False, "Expected ChatCompletionError to propagate"
        except ChatCompletionError:
            pass  # expected
