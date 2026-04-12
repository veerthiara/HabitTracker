"""Tests for habittracker.services.sql.execution_service.

All tests are pure unit tests — no real database connection is needed.
The SQLAlchemy Session is mocked so that session.execute() returns
controllable result objects.

Coverage areas:
  1. Static validation — forbidden keywords (INSERT, UPDATE, DELETE, DROP,
     ALTER, TRUNCATE, CREATE, GRANT, REVOKE) are rejected before execution.
  2. Non-SELECT rejection — statements that do not start with SELECT are
     rejected (comments before SELECT are allowed).
  3. LIMIT injection — queries without a LIMIT clause get MAX_ROWS appended;
     queries that already have a LIMIT are not modified.
  4. Happy-path execution — valid SELECT returns columns, rows, row_count.
  5. Row cap — result set is bounded by MAX_ROWS.
  6. SQLAlchemy errors surface as SqlExecutionError.
  7. user_id is forwarded as a bind parameter.
"""

from __future__ import annotations

import re
import uuid
from unittest.mock import MagicMock, call, patch

import pytest
from sqlalchemy.exc import OperationalError

from habittracker.core.config import SQL_MAX_ROWS
from habittracker.schemas.sql_chat import SqlExecutionRequest, SqlExecutionResult
from habittracker.services.sql.errors import (
    ForbiddenStatementError,
    NonSelectStatementError,
    SqlExecutionError,
)
from habittracker.services.sql.execution_service import SqlExecutionService

# Default service instance used across all happy-path and rejection tests.
_service = SqlExecutionService()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_session(columns: list[str], rows: list[tuple]) -> MagicMock:
    """Return a MagicMock Session whose execute() returns a fake result set."""
    result = MagicMock()
    result.keys.return_value = columns
    result.fetchall.return_value = rows
    session = MagicMock()
    # execute is called twice: once for SET LOCAL, once for the query.
    session.execute.side_effect = [MagicMock(), result]
    return session


def _req(sql: str, user_id: str | None = None) -> SqlExecutionRequest:
    return SqlExecutionRequest(
        sql=sql,
        user_id=user_id or str(uuid.uuid4()),
    )


# ── _validate_static ──────────────────────────────────────────────────────────


class TestValidateStatic:

    @pytest.mark.parametrize(
        "keyword",
        ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
         "TRUNCATE", "CREATE", "GRANT", "REVOKE",
         "insert", "update", "delete"],  # case-insensitive
    )
    def test_forbidden_keyword_raises(self, keyword: str) -> None:
        sql = f"SELECT 1; {keyword} INTO foo VALUES (1)"
        with pytest.raises(ForbiddenStatementError, match=re.escape(keyword)):
            SqlExecutionService._validate_static(sql)

    def test_keyword_inside_column_name_allowed(self) -> None:
        # "deleted_at" contains "delete" but as part of a word — must not raise
        SqlExecutionService._validate_static("SELECT deleted_at FROM habits WHERE user_id = :user_id")

    def test_plain_select_passes(self) -> None:
        SqlExecutionService._validate_static("SELECT id FROM users WHERE user_id = :user_id")

    def test_select_with_leading_whitespace_passes(self) -> None:
        SqlExecutionService._validate_static("   SELECT id FROM users")

    def test_single_line_comment_before_select_passes(self) -> None:
        SqlExecutionService._validate_static("-- find all habits\nSELECT id FROM habits")

    def test_non_select_raises(self) -> None:
        with pytest.raises(NonSelectStatementError):
            SqlExecutionService._validate_static("EXPLAIN SELECT 1")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(NonSelectStatementError):
            SqlExecutionService._validate_static("")


# ── _apply_row_limit ──────────────────────────────────────────────────────────


class TestApplyRowLimit:

    def test_adds_limit_when_absent(self) -> None:
        svc = SqlExecutionService()
        result = svc._apply_row_limit("SELECT id FROM habits")
        assert f"LIMIT {SQL_MAX_ROWS}" in result

    def test_preserves_existing_limit(self) -> None:
        svc = SqlExecutionService()
        sql = "SELECT id FROM habits LIMIT 10"
        assert svc._apply_row_limit(sql) == sql

    def test_existing_limit_case_insensitive(self) -> None:
        svc = SqlExecutionService()
        sql = "SELECT id FROM habits limit 5"
        assert svc._apply_row_limit(sql) == sql

    def test_trailing_semicolon_removed_before_limit(self) -> None:
        svc = SqlExecutionService()
        result = svc._apply_row_limit("SELECT id FROM habits;")
        assert ";" not in result
        assert f"LIMIT {SQL_MAX_ROWS}" in result


# ── execute_sql happy path ────────────────────────────────────────────────────


class TestExecuteSqlHappyPath:

    def test_returns_execution_result(self) -> None:
        session = _mock_session(["id", "name"], [("abc", "Running"), ("def", "Yoga")])
        result = _service.execute(_req("SELECT id, name FROM habits WHERE user_id = :user_id"), session)
        assert isinstance(result, SqlExecutionResult)
        assert result.columns == ["id", "name"]
        assert result.row_count == 2
        assert result.rows[0] == {"id": "abc", "name": "Running"}

    def test_row_count_matches_rows_length(self) -> None:
        session = _mock_session(["id"], [("a",), ("b",), ("c",)])
        result = _service.execute(_req("SELECT id FROM habits WHERE user_id = :user_id"), session)
        assert result.row_count == len(result.rows) == 3

    def test_sql_field_contains_executed_sql(self) -> None:
        session = _mock_session(["id"], [])
        result = _service.execute(_req("SELECT id FROM habits WHERE user_id = :user_id"), session)
        assert "SELECT" in result.sql

    def test_user_id_passed_as_bind_param(self) -> None:
        uid = str(uuid.uuid4())
        session = _mock_session(["id"], [])
        _service.execute(_req("SELECT id FROM habits WHERE user_id = :user_id", uid), session)
        # Second call is the actual query; check bind params include user_id
        query_call = session.execute.call_args_list[1]
        params = query_call[0][1]  # positional arg index 1 = params dict
        assert params["user_id"] == uid

    def test_limit_injected_when_absent(self) -> None:
        session = _mock_session(["id"], [])
        result = _service.execute(_req("SELECT id FROM habits WHERE user_id = :user_id"), session)
        assert f"LIMIT {SQL_MAX_ROWS}" in result.sql

    def test_existing_limit_not_doubled(self) -> None:
        session = _mock_session(["id"], [])
        result = _service.execute(_req("SELECT id FROM habits LIMIT 5"), session)
        assert result.sql.upper().count("LIMIT") == 1

    def test_statement_timeout_set_before_query(self) -> None:
        """SET LOCAL statement_timeout must be the first execute call."""
        session = _mock_session(["id"], [])
        _service.execute(_req("SELECT id FROM habits WHERE user_id = :user_id"), session)
        first_call_sql = str(session.execute.call_args_list[0][0][0])
        assert "statement_timeout" in first_call_sql


# ── execute_sql rejection paths ───────────────────────────────────────────────


class TestExecuteSqlRejection:

    @pytest.mark.parametrize("sql", [
        "INSERT INTO habits (name) VALUES ('bad')",
        "DELETE FROM habits WHERE id = :user_id",
        "DROP TABLE habits",
        "UPDATE habits SET name = 'x'",
        "TRUNCATE habits",
    ])
    def test_forbidden_sql_raises_before_execute(self, sql: str) -> None:
        session = MagicMock()
        with pytest.raises(ForbiddenStatementError):
            _service.execute(_req(sql), session)
        session.execute.assert_not_called()

    def test_non_select_raises_before_execute(self) -> None:
        session = MagicMock()
        with pytest.raises(NonSelectStatementError):
            _service.execute(_req("EXPLAIN SELECT 1"), session)
        session.execute.assert_not_called()


# ── execute_sql database error handling ───────────────────────────────────────


class TestExecuteSqlDbError:

    def test_sqlalchemy_error_raises_execution_error(self) -> None:
        session = MagicMock()
        # First execute (SET LOCAL) succeeds; second (query) raises
        session.execute.side_effect = [
            MagicMock(),
            OperationalError("timeout", {}, Exception("boom")),
        ]
        with pytest.raises(SqlExecutionError):
            _service.execute(_req("SELECT id FROM habits WHERE user_id = :user_id"), session)
