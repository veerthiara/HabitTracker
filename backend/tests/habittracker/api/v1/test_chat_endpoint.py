"""Tests for POST /api/v1/chat endpoint.

Strategy:
  - Use FastAPI TestClient with the full app.
  - Patch `habittracker.api.v1.chat._graph.invoke` so no DB, Ollama, or
    LangGraph orchestration runs — the endpoint's only job is HTTP wiring
    and the 503 guardrail.
  - get_session and get_current_user_id are also overridden so no real
    database connection is required.

All guardrail logic (no-evidence shortcut, answer truncation) is tested in
test_graph_integration.py — not duplicated here.
"""

import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from habittracker.providers.base import ChatCompletionError
from habittracker.schemas.chat import EvidenceItem

# ── App + dependency overrides ────────────────────────────────────────────────

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

# Patch target: the graph singleton's invoke method
_PATCH = "habittracker.api.v1.chat._graph.invoke"

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_graph_result(
    answer: str = "You drank 1800 ml today.",
    intent: str = "bottle_activity",
    used_notes: bool = False,
    evidence=None,
) -> dict:
    """Simulate the state dict returned by graph.invoke()."""
    return {
        "answer": answer,
        "intent": intent,
        "used_notes": used_notes,
        "evidence": evidence or [
            EvidenceItem(type="metric", label="Total hydration today", value="1800 ml")
        ],
    }


# ── Happy path ────────────────────────────────────────────────────────────────


class TestChatEndpointHappyPath:
    @patch(_PATCH)
    def test_returns_200_ok(self, mock_invoke):
        mock_invoke.return_value = _make_graph_result()
        resp = _client.post("/api/v1/chat/", json={"message": "How much water did I drink?"})
        assert resp.status_code == 200

    @patch(_PATCH)
    def test_response_contains_answer(self, mock_invoke):
        mock_invoke.return_value = _make_graph_result(answer="You drank 1800 ml today.")
        resp = _client.post("/api/v1/chat/", json={"message": "How much water?"})
        assert resp.json()["answer"] == "You drank 1800 ml today."

    @patch(_PATCH)
    def test_response_contains_intent(self, mock_invoke):
        mock_invoke.return_value = _make_graph_result(intent="bottle_activity")
        resp = _client.post("/api/v1/chat/", json={"message": "How much water?"})
        assert resp.json()["intent"] == "bottle_activity"

    @patch(_PATCH)
    def test_response_contains_used_notes(self, mock_invoke):
        mock_invoke.return_value = _make_graph_result(used_notes=True)
        resp = _client.post("/api/v1/chat/", json={"message": "Why do I miss habits?"})
        assert resp.json()["used_notes"] is True

    @patch(_PATCH)
    def test_response_contains_evidence_list(self, mock_invoke):
        mock_invoke.return_value = _make_graph_result()
        resp = _client.post("/api/v1/chat/", json={"message": "How much water?"})
        assert isinstance(resp.json()["evidence"], list)
        assert len(resp.json()["evidence"]) > 0

    @patch(_PATCH)
    def test_response_contains_thread_id(self, mock_invoke):
        """Endpoint must always return a thread_id (generated if not provided)."""
        mock_invoke.return_value = _make_graph_result()
        resp = _client.post("/api/v1/chat/", json={"message": "How much water?"})
        assert "thread_id" in resp.json()
        assert resp.json()["thread_id"] is not None

    @patch(_PATCH)
    def test_client_thread_id_echoed_in_response(self, mock_invoke):
        """A thread_id supplied in the request must be echoed back."""
        mock_invoke.return_value = _make_graph_result()
        tid = str(uuid.uuid4())
        resp = _client.post("/api/v1/chat/", json={"message": "How much water?", "thread_id": tid})
        assert resp.json()["thread_id"] == tid

    @patch(_PATCH)
    def test_graph_invoke_called_once(self, mock_invoke):
        mock_invoke.return_value = _make_graph_result()
        _client.post("/api/v1/chat/", json={"message": "How much water?"})
        assert mock_invoke.call_count == 1


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

    @patch(_PATCH)
    def test_message_at_max_length_accepted(self, mock_invoke):
        mock_invoke.return_value = _make_graph_result()
        resp = _client.post("/api/v1/chat/", json={"message": "x" * 500})
        assert resp.status_code == 200


# ── Guardrail: Ollama unavailable → HTTP 503 ─────────────────────────────────


class TestChatEndpointGuardrails:
    @patch(_PATCH)
    def test_chat_completion_error_returns_503(self, mock_invoke):
        mock_invoke.side_effect = ChatCompletionError("Ollama is down")
        resp = _client.post("/api/v1/chat/", json={"message": "How much water?"})
        assert resp.status_code == 503

    @patch(_PATCH)
    def test_503_response_has_detail(self, mock_invoke):
        mock_invoke.side_effect = ChatCompletionError("Ollama is down")
        resp = _client.post("/api/v1/chat/", json={"message": "How much water?"})
        body = resp.json()
        assert "detail" in body
        assert "Ollama" in body["detail"]
