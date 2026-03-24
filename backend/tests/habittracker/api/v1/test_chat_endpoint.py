"""Tests for POST /api/v1/chat endpoint.

Strategy:
  - Use FastAPI TestClient with the full app.
  - Patch `habittracker.api.v1.chat.handle_chat` so no DB, Ollama, or
    intent/context logic runs — the endpoint's only job is HTTP wiring
    and the 503 guardrail.
  - get_session and get_current_user_id are also overridden so no real
    database connection is required.

All guardrail logic (no-evidence shortcut, answer truncation) is tested in
test_chat_service.py — not duplicated here.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from habittracker.providers.base import ChatCompletionError
from habittracker.schemas.chat import ChatResponse, EvidenceItem

# ── App + dependency overrides ────────────────────────────────────────────────
# Import the app via the factory used in production, but override the two
# FastAPI dependencies that would require a real DB/auth.

from habittracker.server import create_application

_app = create_application()

_DEMO_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _override_get_session():
    yield MagicMock()


def _override_get_user_id():
    return _DEMO_USER_ID


from habittracker.api.deps import get_current_user_id
from habittracker.models.repository.session import get_session

_app.dependency_overrides[get_session] = _override_get_session
_app.dependency_overrides[get_current_user_id] = _override_get_user_id

_client = TestClient(_app, raise_server_exceptions=False)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_chat_response(
    answer: str = "You drank 1800 ml today.",
    intent: str = "bottle_activity",
    used_notes: bool = False,
    evidence=None,
) -> ChatResponse:
    return ChatResponse(
        answer=answer,
        intent=intent,
        used_notes=used_notes,
        evidence=evidence or [
            EvidenceItem(type="metric", label="Total hydration today", value="1800 ml")
        ],
    )


# ── Happy path ────────────────────────────────────────────────────────────────


class TestChatEndpointHappyPath:
    @patch("habittracker.api.v1.chat.handle_chat")
    def test_returns_200_ok(self, mock_handle):
        mock_handle.return_value = _make_chat_response()
        resp = _client.post("/api/v1/chat/", json={"message": "How much water did I drink?"})
        assert resp.status_code == 200

    @patch("habittracker.api.v1.chat.handle_chat")
    def test_response_contains_answer(self, mock_handle):
        mock_handle.return_value = _make_chat_response(answer="You drank 1800 ml today.")
        resp = _client.post("/api/v1/chat/", json={"message": "How much water?"})
        assert resp.json()["answer"] == "You drank 1800 ml today."

    @patch("habittracker.api.v1.chat.handle_chat")
    def test_response_contains_intent(self, mock_handle):
        mock_handle.return_value = _make_chat_response(intent="bottle_activity")
        resp = _client.post("/api/v1/chat/", json={"message": "How much water?"})
        assert resp.json()["intent"] == "bottle_activity"

    @patch("habittracker.api.v1.chat.handle_chat")
    def test_response_contains_used_notes(self, mock_handle):
        mock_handle.return_value = _make_chat_response(used_notes=True)
        resp = _client.post("/api/v1/chat/", json={"message": "Why do I miss habits?"})
        assert resp.json()["used_notes"] is True

    @patch("habittracker.api.v1.chat.handle_chat")
    def test_response_contains_evidence_list(self, mock_handle):
        mock_handle.return_value = _make_chat_response()
        resp = _client.post("/api/v1/chat/", json={"message": "How much water?"})
        assert isinstance(resp.json()["evidence"], list)
        assert len(resp.json()["evidence"]) > 0

    @patch("habittracker.api.v1.chat.handle_chat")
    def test_handle_chat_called_once(self, mock_handle):
        mock_handle.return_value = _make_chat_response()
        _client.post("/api/v1/chat/", json={"message": "How much water?"})
        assert mock_handle.call_count == 1


# ── Request validation ────────────────────────────────────────────────────────


class TestChatEndpointValidation:
    def test_empty_message_returns_422(self):
        resp = _client.post("/api/v1/chat/", json={"message": ""})
        assert resp.status_code == 422

    def test_missing_message_returns_422(self):
        resp = _client.post("/api/v1/chat/", json={})
        assert resp.status_code == 422

    def test_message_too_long_returns_422(self):
        resp = _client.post("/api/v1/chat/", json={"message": "x" * 501})
        assert resp.status_code == 422

    @patch("habittracker.api.v1.chat.handle_chat")
    def test_message_at_max_length_accepted(self, mock_handle):
        mock_handle.return_value = _make_chat_response()
        resp = _client.post("/api/v1/chat/", json={"message": "x" * 500})
        assert resp.status_code == 200


# ── Guardrail: Ollama unavailable → HTTP 503 ─────────────────────────────────


class TestChatEndpointGuardrails:
    @patch("habittracker.api.v1.chat.handle_chat")
    def test_chat_completion_error_returns_503(self, mock_handle):
        mock_handle.side_effect = ChatCompletionError("Ollama is down")
        resp = _client.post("/api/v1/chat/", json={"message": "How much water?"})
        assert resp.status_code == 503

    @patch("habittracker.api.v1.chat.handle_chat")
    def test_503_response_has_detail(self, mock_handle):
        mock_handle.side_effect = ChatCompletionError("Ollama is down")
        resp = _client.post("/api/v1/chat/", json={"message": "How much water?"})
        body = resp.json()
        assert "detail" in body
        assert "Ollama" in body["detail"]
