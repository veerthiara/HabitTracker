"""Tests for scripts.embed.service.

All external dependencies (DB session, embedding provider) are mocked
so tests run without Postgres or Ollama.
"""

import uuid
from unittest.mock import MagicMock, call, patch

import pytest

from scripts.embed.providers.base import EmbeddingError, EmbeddingProvider
from scripts.embed.repository import NoteRow
from scripts.embed.service import EmbedResult, embed_notes


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_note(content: str = "test") -> NoteRow:
    return NoteRow(id=uuid.uuid4(), content=content)


def _make_provider(dims: int = 768) -> EmbeddingProvider:
    provider = MagicMock(spec=EmbeddingProvider)
    provider.embed.return_value = [0.1] * dims
    provider.dimensions = dims
    return provider


def _make_session() -> MagicMock:
    session = MagicMock()
    session.commit = MagicMock()
    return session


# ── Basic behaviour ───────────────────────────────────────────────────────────

class TestEmbedNotesBasic:
    def test_no_notes_returns_zero_counts(self) -> None:
        session = _make_session()
        provider = _make_provider()
        with patch("scripts.embed.service.fetch_unembedded_notes", return_value=[]):
            result = embed_notes(session, provider)
        assert result.processed == 0
        assert result.errors == 0
        assert result.skipped == 0

    def test_no_notes_success_is_true(self) -> None:
        session = _make_session()
        provider = _make_provider()
        with patch("scripts.embed.service.fetch_unembedded_notes", return_value=[]):
            result = embed_notes(session, provider)
        assert result.success is True

    def test_single_note_processed(self) -> None:
        session = _make_session()
        provider = _make_provider(dims=768)
        notes = [_make_note()]
        with (
            patch("scripts.embed.service.fetch_unembedded_notes", return_value=notes),
            patch("scripts.embed.service.update_note_embedding") as mock_update,
        ):
            result = embed_notes(session, provider, expected_dims=768)
        assert result.processed == 1
        assert result.errors == 0
        mock_update.assert_called_once()

    def test_commit_called_per_batch(self) -> None:
        session = _make_session()
        provider = _make_provider(dims=3)
        notes = [_make_note() for _ in range(6)]
        with (
            patch("scripts.embed.service.fetch_unembedded_notes", return_value=notes),
            patch("scripts.embed.service.update_note_embedding"),
        ):
            embed_notes(session, provider, batch_size=2, expected_dims=3, inter_batch_delay=0)
        # 6 notes / batch_size 2 → 3 commits
        assert session.commit.call_count == 3


# ── Error handling ────────────────────────────────────────────────────────────

class TestEmbedNotesErrors:
    def test_embedding_error_counts_as_error(self) -> None:
        session = _make_session()
        provider = _make_provider()
        provider.embed.side_effect = EmbeddingError("ollama down")
        notes = [_make_note()]
        with patch("scripts.embed.service.fetch_unembedded_notes", return_value=notes):
            result = embed_notes(session, provider, expected_dims=768)
        assert result.errors == 1
        assert result.processed == 0
        assert result.success is False

    def test_failed_note_id_recorded(self) -> None:
        session = _make_session()
        note = _make_note()
        provider = _make_provider()
        provider.embed.side_effect = EmbeddingError("fail")
        with patch("scripts.embed.service.fetch_unembedded_notes", return_value=[note]):
            result = embed_notes(session, provider, expected_dims=768)
        assert str(note.id) in result.error_ids

    def test_one_error_does_not_stop_others(self) -> None:
        session = _make_session()
        provider = _make_provider(dims=768)
        notes = [_make_note("a"), _make_note("b"), _make_note("c")]
        provider.embed.side_effect = [
            EmbeddingError("fail"),
            [0.1] * 768,
            [0.1] * 768,
        ]
        with (
            patch("scripts.embed.service.fetch_unembedded_notes", return_value=notes),
            patch("scripts.embed.service.update_note_embedding"),
        ):
            result = embed_notes(session, provider, expected_dims=768)
        assert result.processed == 2
        assert result.errors == 1


# ── Dimension validation ──────────────────────────────────────────────────────

class TestDimensionValidation:
    def test_wrong_dims_skips_note(self) -> None:
        session = _make_session()
        provider = _make_provider(dims=512)  # returns 512 but we expect 768
        notes = [_make_note()]
        with (
            patch("scripts.embed.service.fetch_unembedded_notes", return_value=notes),
            patch("scripts.embed.service.update_note_embedding") as mock_update,
        ):
            result = embed_notes(session, provider, expected_dims=768)
        assert result.skipped == 1
        assert result.processed == 0
        mock_update.assert_not_called()

    def test_correct_dims_writes_embedding(self) -> None:
        session = _make_session()
        provider = _make_provider(dims=768)
        notes = [_make_note()]
        with (
            patch("scripts.embed.service.fetch_unembedded_notes", return_value=notes),
            patch("scripts.embed.service.update_note_embedding") as mock_update,
        ):
            result = embed_notes(session, provider, expected_dims=768)
        assert result.processed == 1
        mock_update.assert_called_once()


# ── EmbedResult ───────────────────────────────────────────────────────────────

class TestEmbedResult:
    def test_success_true_when_no_errors(self) -> None:
        r = EmbedResult(processed=5, skipped=0, errors=0)
        assert r.success is True

    def test_success_false_when_errors(self) -> None:
        r = EmbedResult(processed=3, errors=2)
        assert r.success is False

    def test_error_ids_defaults_empty(self) -> None:
        r = EmbedResult()
        assert r.error_ids == []
