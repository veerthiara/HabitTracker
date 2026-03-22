"""Tests for scripts.embed.providers.ollama.

All tests mock httpx so no real Ollama server is needed.
"""

import pytest
import httpx
from unittest.mock import MagicMock, patch

from scripts.embed.providers.base import EmbeddingError
from scripts.embed.providers.ollama import OllamaProvider

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


class TestOllamaProviderSuccess:
    def test_returns_vector_on_success(self) -> None:
        provider = _make_provider()
        with patch.object(provider._client, "post", return_value=_mock_response(_FAKE_VECTOR)):
            result = provider.embed("hello world")
        assert result == _FAKE_VECTOR

    def test_dimensions_property(self) -> None:
        provider = _make_provider(expected_dims=768)
        assert provider.dimensions == 768

    def test_calls_correct_endpoint(self) -> None:
        provider = _make_provider()
        mock_post = MagicMock(return_value=_mock_response(_FAKE_VECTOR))
        with patch.object(provider._client, "post", mock_post):
            provider.embed("test")
        url = mock_post.call_args[0][0]
        assert url == "http://localhost:11434/api/embeddings"

    def test_sends_model_and_prompt(self) -> None:
        provider = _make_provider(model="nomic-embed-text")
        mock_post = MagicMock(return_value=_mock_response(_FAKE_VECTOR))
        with patch.object(provider._client, "post", mock_post):
            provider.embed("my text")
        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == "nomic-embed-text"
        assert payload["prompt"] == "my text"


class TestOllamaProviderErrors:
    def test_raises_embedding_error_on_missing_key(self) -> None:
        provider = _make_provider()
        bad_resp = MagicMock(spec=httpx.Response)
        bad_resp.status_code = 200
        bad_resp.json.return_value = {"result": "no embedding key"}
        bad_resp.raise_for_status = MagicMock()
        with patch.object(provider._client, "post", return_value=bad_resp):
            with pytest.raises(EmbeddingError, match="missing 'embedding'"):
                provider.embed("text")

    def test_raises_embedding_error_on_4xx(self) -> None:
        provider = _make_provider()
        err_resp = MagicMock(spec=httpx.Response)
        err_resp.status_code = 400
        err_resp.text = "bad request"
        http_err = httpx.HTTPStatusError("bad request", request=MagicMock(), response=err_resp)
        err_resp.raise_for_status.side_effect = http_err
        with patch.object(provider._client, "post", return_value=err_resp):
            with pytest.raises(EmbeddingError, match="400"):
                provider.embed("text")

    def test_retries_on_5xx_then_raises(self) -> None:
        provider = _make_provider(max_retries=2, retry_backoff=0.0)
        err_resp = MagicMock(spec=httpx.Response)
        err_resp.status_code = 500
        err_resp.text = "internal error"
        http_err = httpx.HTTPStatusError("server error", request=MagicMock(), response=err_resp)
        err_resp.raise_for_status.side_effect = http_err

        call_count = 0

        def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return err_resp

        with patch.object(provider._client, "post", side_effect=_side_effect):
            with pytest.raises(EmbeddingError):
                provider.embed("text")

        # max_retries=2 → 3 total attempts
        assert call_count == 3

    def test_retries_on_connect_error(self) -> None:
        provider = _make_provider(max_retries=1, retry_backoff=0.0)
        connect_err = httpx.ConnectError("connection refused")
        with patch.object(provider._client, "post", side_effect=connect_err):
            with pytest.raises(EmbeddingError, match="after 2 attempt"):
                provider.embed("text")
