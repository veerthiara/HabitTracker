"""Tests for habittracker.providers.ollama.

All tests mock httpx.Client.post so no real Ollama server is needed.
"""

import pytest
import httpx
from unittest.mock import MagicMock, patch

from habittracker.providers.base import EmbeddingError
from habittracker.providers.ollama import OllamaProvider

_FAKE_VECTOR = [0.1] * 768


def _make_provider(**kwargs) -> OllamaProvider:
    defaults = dict(
        base_url="http://localhost:11434",
        model="nomic-embed-text",
        timeout=10.0,
        max_retries=1,
        retry_backoff=0.0,
        expected_dims=768,
    )
    defaults.update(kwargs)
    return OllamaProvider(**defaults)


def _mock_response(vector: list[float]) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {"embedding": vector}
    resp.raise_for_status = MagicMock()
    return resp


# ── Success path ──────────────────────────────────────────────────────────────

class TestOllamaProviderSuccess:
    @patch("httpx.Client.post")
    def test_returns_vector_on_success(self, mock_post) -> None:
        mock_post.return_value = _mock_response(_FAKE_VECTOR)
        result = _make_provider().embed("hello world")
        assert result == _FAKE_VECTOR

    def test_dimensions_property(self) -> None:
        assert _make_provider(expected_dims=768).dimensions == 768

    @patch("httpx.Client.post")
    def test_calls_correct_endpoint(self, mock_post) -> None:
        mock_post.return_value = _mock_response(_FAKE_VECTOR)
        _make_provider().embed("test")
        assert mock_post.call_args[0][0] == "http://localhost:11434/api/embeddings"

    @patch("httpx.Client.post")
    def test_sends_model_and_prompt(self, mock_post) -> None:
        mock_post.return_value = _mock_response(_FAKE_VECTOR)
        _make_provider(model="nomic-embed-text").embed("my text")
        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == "nomic-embed-text"
        assert payload["prompt"] == "my text"


# ── Error handling ────────────────────────────────────────────────────────────

class TestOllamaProviderErrors:
    @patch("httpx.Client.post")
    def test_raises_embedding_error_on_missing_key(self, mock_post) -> None:
        bad_resp = MagicMock(spec=httpx.Response)
        bad_resp.status_code = 200
        bad_resp.json.return_value = {"result": "no embedding key"}
        bad_resp.raise_for_status = MagicMock()
        mock_post.return_value = bad_resp
        with pytest.raises(EmbeddingError, match="missing 'embedding'"):
            _make_provider().embed("text")

    @patch("httpx.Client.post")
    def test_raises_embedding_error_on_4xx(self, mock_post) -> None:
        err_resp = MagicMock(spec=httpx.Response)
        err_resp.status_code = 400
        err_resp.text = "bad request"
        err_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "bad request", request=MagicMock(), response=err_resp
        )
        mock_post.return_value = err_resp
        with pytest.raises(EmbeddingError, match="400"):
            _make_provider().embed("text")

    @patch("httpx.Client.post")
    def test_retries_on_5xx_then_raises(self, mock_post) -> None:
        err_resp = MagicMock(spec=httpx.Response)
        err_resp.status_code = 500
        err_resp.text = "internal error"
        err_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "server error", request=MagicMock(), response=err_resp
        )
        mock_post.return_value = err_resp
        with pytest.raises(EmbeddingError):
            _make_provider(max_retries=2, retry_backoff=0.0).embed("text")
        # max_retries=2 → 3 total attempts
        assert mock_post.call_count == 3

    @patch("httpx.Client.post")
    def test_retries_on_connect_error(self, mock_post) -> None:
        mock_post.side_effect = httpx.ConnectError("connection refused")
        with pytest.raises(EmbeddingError, match="after 2 attempt"):
            _make_provider(max_retries=1, retry_backoff=0.0).embed("text")
