"""Tests for habittracker.providers.ollama_chat.

All tests mock httpx.Client.post so no real Ollama server is needed.
Mirrors the structure of test_ollama.py for consistency.
"""

import pytest
import httpx
from unittest.mock import MagicMock, patch

from habittracker.providers.base import ChatCompletionError
from habittracker.providers.ollama_chat import OllamaChatProvider

_FAKE_ANSWER = "You completed 3 habits today."


def _make_provider(**kwargs) -> OllamaChatProvider:
    defaults = dict(
        base_url="http://localhost:11434",
        model="llama3.2",
        timeout=10.0,
        max_retries=1,
        retry_backoff=0.0,
    )
    defaults.update(kwargs)
    return OllamaChatProvider(**defaults)


def _mock_response(content: str) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {"message": {"content": content, "role": "assistant"}}
    resp.raise_for_status = MagicMock()
    return resp


# ── Success path ──────────────────────────────────────────────────────────────

class TestOllamaChatProviderSuccess:
    @patch("httpx.Client.post")
    def test_returns_content_on_success(self, mock_post) -> None:
        mock_post.return_value = _mock_response(_FAKE_ANSWER)
        result = _make_provider().complete("You are helpful.", "How did I do today?")
        assert result == _FAKE_ANSWER

    @patch("httpx.Client.post")
    def test_calls_correct_endpoint(self, mock_post) -> None:
        mock_post.return_value = _mock_response(_FAKE_ANSWER)
        _make_provider().complete("system", "user")
        assert mock_post.call_args[0][0] == "http://localhost:11434/api/chat"

    @patch("httpx.Client.post")
    def test_sends_correct_payload(self, mock_post) -> None:
        mock_post.return_value = _mock_response(_FAKE_ANSWER)
        _make_provider(model="llama3.2").complete("sys prompt", "user msg")
        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == "llama3.2"
        assert payload["stream"] is False
        assert payload["messages"][0] == {"role": "system", "content": "sys prompt"}
        assert payload["messages"][1] == {"role": "user", "content": "user msg"}

    @patch("httpx.Client.post")
    def test_returns_string(self, mock_post) -> None:
        mock_post.return_value = _mock_response("ok")
        assert isinstance(_make_provider().complete("s", "u"), str)


# ── Error handling ────────────────────────────────────────────────────────────

class TestOllamaChatProviderErrors:
    @patch("httpx.Client.post")
    def test_raises_on_missing_message_key(self, mock_post) -> None:
        bad_resp = MagicMock(spec=httpx.Response)
        bad_resp.status_code = 200
        bad_resp.json.return_value = {"done": True}  # no 'message' key
        bad_resp.raise_for_status = MagicMock()
        mock_post.return_value = bad_resp
        with pytest.raises(ChatCompletionError, match="message.content"):
            _make_provider().complete("s", "u")

    @patch("httpx.Client.post")
    def test_raises_on_missing_content_key(self, mock_post) -> None:
        bad_resp = MagicMock(spec=httpx.Response)
        bad_resp.status_code = 200
        bad_resp.json.return_value = {"message": {"role": "assistant"}}  # no 'content'
        bad_resp.raise_for_status = MagicMock()
        mock_post.return_value = bad_resp
        with pytest.raises(ChatCompletionError, match="message.content"):
            _make_provider().complete("s", "u")

    @patch("httpx.Client.post")
    def test_raises_immediately_on_4xx(self, mock_post) -> None:
        err_resp = MagicMock(spec=httpx.Response)
        err_resp.status_code = 400
        err_resp.text = "bad request"
        err_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "bad request", request=MagicMock(), response=err_resp
        )
        mock_post.return_value = err_resp
        with pytest.raises(ChatCompletionError, match="400"):
            _make_provider(max_retries=3).complete("s", "u")

    @patch("httpx.Client.post")
    def test_retries_on_5xx_then_raises(self, mock_post) -> None:
        err_resp = MagicMock(spec=httpx.Response)
        err_resp.status_code = 500
        err_resp.text = "internal error"
        err_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "server error", request=MagicMock(), response=err_resp
        )
        mock_post.return_value = err_resp
        with pytest.raises(ChatCompletionError):
            _make_provider(max_retries=2, retry_backoff=0.0).complete("s", "u")
        # max_retries=2 → 3 total attempts
        assert mock_post.call_count == 3

    @patch("httpx.Client.post")
    def test_retries_on_connect_error(self, mock_post) -> None:
        mock_post.side_effect = httpx.ConnectError("connection refused")
        with pytest.raises(ChatCompletionError, match="after 2 attempt"):
            _make_provider(max_retries=1, retry_backoff=0.0).complete("s", "u")

    @patch("httpx.Client.post")
    def test_timeout_not_retried(self, mock_post) -> None:
        """Timeouts are not retried — local LLMs can hang indefinitely."""
        mock_post.side_effect = httpx.TimeoutException("timed out")
        with pytest.raises(ChatCompletionError, match="timed out"):
            _make_provider(max_retries=3, retry_backoff=0.0).complete("s", "u")
        # Must not retry on timeout
        assert mock_post.call_count == 1


# ── Contract ──────────────────────────────────────────────────────────────────

class TestChatCompletionError:
    def test_is_runtime_error(self) -> None:
        assert isinstance(ChatCompletionError("something went wrong"), RuntimeError)

    def test_message_preserved(self) -> None:
        assert "fail msg" in str(ChatCompletionError("fail msg"))

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(ChatCompletionError, match="boom"):
            raise ChatCompletionError("boom")
