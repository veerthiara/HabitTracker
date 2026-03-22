"""Tests for scripts.embed.providers.base.

Verifies the EmbeddingProvider contract and EmbeddingError.
"""

import pytest

from scripts.embed.providers.base import EmbeddingError, EmbeddingProvider


class _ConcreteProvider(EmbeddingProvider):
    """Minimal concrete implementation used only in these tests."""

    def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    @property
    def dimensions(self) -> int:
        return 3


class TestEmbeddingProvider:
    def test_embed_returns_floats(self) -> None:
        provider = _ConcreteProvider()
        result = provider.embed("hello")
        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    def test_dimensions_matches_embed_output(self) -> None:
        provider = _ConcreteProvider()
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
