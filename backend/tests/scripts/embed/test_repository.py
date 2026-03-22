"""Tests for scripts.embed.repository.

Uses an in-memory SQLite database — no Postgres or migrations required.
The tests cover the helper functions directly, not end-to-end behaviour.
"""

import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from scripts.embed.repository import NoteRow, fetch_unembedded_notes, vector_to_literal


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def sqlite_session():
    """Provide a minimal in-memory SQLite session with a notes-like table.

    Note: SQLite does not have the vector type, so update_note_embedding
    cannot be tested here. That path is exercised by test_service.py via mocks.
    """
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE TABLE notes ("
            "  id TEXT PRIMARY KEY,"
            "  content TEXT NOT NULL,"
            "  embedding TEXT,"
            "  created_at TEXT DEFAULT CURRENT_TIMESTAMP"
            ")"
        ))
        conn.commit()
    Session_ = sessionmaker(bind=engine)
    session = Session_()
    yield session
    session.close()


def _insert_note(session, note_id: str, content: str, embedding=None) -> None:
    session.execute(
        text("INSERT INTO notes (id, content, embedding) VALUES (:id, :content, :emb)"),
        {"id": note_id, "content": content, "emb": embedding},
    )
    session.commit()


# ── vector_to_literal ─────────────────────────────────────────────────────────

class TestVectorToLiteral:
    def test_empty_list(self) -> None:
        assert vector_to_literal([]) == "[]"

    def test_single_value(self) -> None:
        assert vector_to_literal([1.0]) == "[1.0]"

    def test_multiple_values(self) -> None:
        result = vector_to_literal([0.1, 0.2, 0.3])
        assert result == "[0.1,0.2,0.3]"

    def test_negative_values(self) -> None:
        result = vector_to_literal([-0.5, 0.5])
        assert "-0.5" in result
        assert "0.5" in result

    def test_returns_string(self) -> None:
        assert isinstance(vector_to_literal([1.0, 2.0]), str)

    def test_brackets(self) -> None:
        result = vector_to_literal([1.0, 2.0])
        assert result.startswith("[")
        assert result.endswith("]")

    def test_large_vector(self) -> None:
        vec = [float(i) / 1000 for i in range(768)]
        result = vector_to_literal(vec)
        assert result.startswith("[")
        assert result.count(",") == 767


# ── fetch_unembedded_notes ────────────────────────────────────────────────────

class TestFetchUnembeddedNotes:
    def test_returns_empty_when_all_embedded(self, sqlite_session) -> None:
        _insert_note(sqlite_session, str(uuid.uuid4()), "note", embedding="[0.1]")
        result = fetch_unembedded_notes(sqlite_session)
        assert result == []

    def test_returns_note_with_null_embedding(self, sqlite_session) -> None:
        note_id = str(uuid.uuid4())
        _insert_note(sqlite_session, note_id, "unembedded note")
        result = fetch_unembedded_notes(sqlite_session)
        assert len(result) == 1
        assert isinstance(result[0], NoteRow)

    def test_excludes_already_embedded(self, sqlite_session) -> None:
        id1, id2 = str(uuid.uuid4()), str(uuid.uuid4())
        _insert_note(sqlite_session, id1, "needs embedding")
        _insert_note(sqlite_session, id2, "already done", embedding="[0.1]")
        result = fetch_unembedded_notes(sqlite_session)
        assert len(result) == 1

    def test_note_row_fields(self, sqlite_session) -> None:
        note_id = str(uuid.uuid4())
        _insert_note(sqlite_session, note_id, "hello")
        rows = fetch_unembedded_notes(sqlite_session)
        assert rows[0].content == "hello"
