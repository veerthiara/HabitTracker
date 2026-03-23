"""Tests for habittracker.services.embedding_service.

All external dependencies (DB session, embedding provider) are mocked
so tests run without Postgres or Ollama.

Patch decorator stacking order: decorators are applied bottom-up, so the
bottom @patch's mock is passed as the first argument after self.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from habittracker.providers.base import EmbeddingError, EmbeddingProvider
from habittracker.models.repository.embedding_repository import NoteRow
from habittracker.services.embedding_service import EmbedResult, embed_notes

_FETCH = "habittracker.services.embedding_service.fetch_unembedded_notes"
_UPDATE = "habittracker.services.embedding_service.update_note_embedding"


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
    @patch(_FETCH, return_value=[])
    def test_no_notes_returns_zero_counts(self, _mock_fetch) -> None:
        result = embed_notes(_make_session(), _make_provider())
        assert result.processed == 0
        assert result.errors == 0
        assert result.skipped == 0

    @patch(_FETCH, return_value=[])
    def test_no_notes_success_is_true(self, _mock_fetch) -> None:
        assert embed_notes(_make_session(), _make_provider()).success is True

    @patch(_UPDATE)
    @patch(_FETCH)
    def test_single_note_processed(self, mock_fetch, mock_update) -> None:
        mock_fetch.return_value = [_make_note()]
        result = embed_notes(_make_session(), _make_provider(dims=768), expected_dims=768)
        assert result.processed == 1
        assert result.errors == 0
        mock_update.assert_called_once()

    @patch(_UPDATE)
    @patch(_FETCH)
    def test_commit_called_per_batch(self, mock_fetch, _mock_update) -> None:
        session = _make_session()
        mock_fetch.return_value = [_make_note() for _ in range(6)]
        embed_notes(session, _make_provider(dims=3), batch_size=2, expected_dims=3, inter_batch_delay=0)
        # 6 notes / batch_size 2 → 3 commits
        assert session.commit.call_count == 3


# ── Error handling ────────────────────────────────────────────────────────────

class TestEmbedNotesErrors:
    @patch(_FETCH)
    def test_embedding_error_counts_as_error(self, mock_fetch) -> None:
        provider = _make_provider()
        provider.embed.side_effect = EmbeddingError("ollama down")
        mock_fetch.return_value = [_make_note()]
        result = embed_notes(_make_session(), provider, expected_dims=768)
        assert result.errors == 1
        assert result.processed == 0
        assert result.success is False

    @patch(_FETCH)
    def test_failed_note_id_recorded(self, mock_fetch) -> None:
        note = _make_note()
        provider = _make_provider()
        provider.embed.side_effect = EmbeddingError("fail")
        mock_fetch.return_value = [note]
        result = embed_notes(_make_session(), provider, expected_dims=768)
        assert str(note.id) in result.error_ids

    @patch(_UPDATE)
    @patch(_FETCH)
    def test_one_error_does_not_stop_others(self, mock_fetch, _mock_update) -> None:
        provider = _make_provider(dims=768)
        provider.embed.side_effect = [EmbeddingError("fail"), [0.1] * 768, [0.1] * 768]
        mock_fetch.return_value = [_make_note("a"), _make_note("b"), _make_note("c")]
        result = embed_notes(_make_session(), provider, expected_dims=768)
        assert result.processed == 2
        assert result.errors == 1


# ── Dimension validation ──────────────────────────────────────────────────────

class TestDimensionValidation:
    @patch(_UPDATE)
    @patch(_FETCH)
    def test_wrong_dims_skips_note(self, mock_fetch, mock_update) -> None:
        mock_fetch.return_value = [_make_note()]
        result = embed_notes(_make_session(), _make_provider(dims=512), expected_dims=768)
        assert result.skipped == 1
        assert result.processed == 0
        mock_update.assert_not_called()

    @patch(_UPDATE)
    @patch(_FETCH)
    def test_correct_dims_writes_embedding(self, mock_fetch, mock_update) -> None:
        mock_fetch.return_value = [_make_note()]
        result = embed_notes(_make_session(), _make_provider(dims=768), expected_dims=768)
        assert result.processed == 1
        mock_update.assert_called_once()


# ── EmbedResult ───────────────────────────────────────────────────────────────

class TestEmbedResult:
    def test_success_true_when_no_errors(self) -> None:
        assert EmbedResult(processed=5, skipped=0, errors=0).success is True

    def test_success_false_when_errors(self) -> None:
        assert EmbedResult(processed=3, errors=2).success is False

    def test_error_ids_defaults_empty(self) -> None:
        assert EmbedResult().error_ids == []
