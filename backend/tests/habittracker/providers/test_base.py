"""Tests for habittracker.providers.base.

Verifies the EmbeddingProvider / ChatProvider contracts and their error types.
"""

import pytest

from habittracker.providers.base import (
    ChatCompletionError,
    ChatProvider,
    EmbeddingError,
    EmbeddingProvider,
)


# ── EmbeddingProvider ─────────────────────────────────────────────────────────

class _ConcreteEmbeddingProvider(EmbeddingProvider):
    """Minimal concrete embedding provider used only in these tests."""

    def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    @property
    def dimensions(self) -> int:
        return 3


class TestEmbeddingProvider:
    def test_embed_returns_floats(self) -> None:
        provider = _ConcreteEmbeddingProvider()
        result = provider.embed("hello")
        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    def test_dimensions_matches_embed_output(self) -> None:
        provider = _ConcreteEmbeddingProvider()
        assert provider.dimensions == len(provider.embed("x"))


class TestEmbeddingError:
    def test_is_runtime_error(self) -> None:
        err = EmbeddingError("something went wrong")
        assert isinstance(err, RuntimeError)

    def test_message_preserved(self) -> None:
        err = EmbeddingError("fail msg")
        assert "fail msg" in str(err)

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(EmbeddingError, match="boom"):
            raise EmbeddingError("boom")


# ── ChatProvider ──────────────────────────────────────────────────────────────

class _ConcreteChatProvider(ChatProvider):
    """Minimal concrete chat provider used only in these tests."""

    def complete(self, system: str, user: str) -> str:
        return f"echo: {user}"


class TestChatProvider:
    def test_complete_returns_string(self) -> None:
        provider = _ConcreteChatProvider()
        result = provider.complete("You are helpful.", "hello")
        assert isinstance(result, str)

    def test_complete_uses_both_args(self) -> None:
        provider = _ConcreteChatProvider()
        result = provider.complete("sys", "my question")
        assert "my question" in result


class TestChatCompletionError:
    def test_is_runtime_error(self) -> None:
        err = ChatCompletionError("something went wrong")
        assert isinstance(err, RuntimeError)

    def test_message_preserved(self) -> None:
        err = ChatCompletionError("fail msg")
        assert "fail msg" in str(err)

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(ChatCompletionError, match="boom"):
            raise ChatCompletionError("boom")
