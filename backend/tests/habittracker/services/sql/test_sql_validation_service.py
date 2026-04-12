"""Tests for habittracker.services.sql.validation_service.

All tests are pure unit tests — no database or LLM is required.

Coverage areas:
  1. Single-statement check — mid-query semicolons are rejected;
     trailing semicolons are allowed.
  2. SELECT-only check — non-SELECT and forbidden keywords are rejected.
  3. Allowed-tables check — unknown tables are rejected; approved tables pass.
  4. validate() — returns OK for a valid query; REJECTED for each failure mode.
  5. Ordering — single-statement is checked before SELECT, SELECT before tables.
  6. Singleton — sql_validation_service is accessible from the module.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from habittracker.schemas.sql_chat import ValidationStatus
from habittracker.services.sql.validation_service import SqlValidationService, sql_validation_service


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_service(allowed: list[str] | None = None) -> SqlValidationService:
    """Return a service with a controlled approved-tables list."""
    schema_svc = MagicMock()
    schema_svc.allowed_tables = allowed or ["habits", "habit_logs", "users"]
    return SqlValidationService(schema_svc=schema_svc)


# ── Single-statement check ────────────────────────────────────────────────────


class TestCheckSingleStatement:

    def test_no_semicolon_ok(self) -> None:
        assert SqlValidationService._check_single_statement(
            "SELECT id FROM habits WHERE user_id = :user_id"
        ) is None

    def test_trailing_semicolon_ok(self) -> None:
        assert SqlValidationService._check_single_statement(
            "SELECT id FROM habits WHERE user_id = :user_id;"
        ) is None

    def test_trailing_semicolon_with_whitespace_ok(self) -> None:
        assert SqlValidationService._check_single_statement(
            "SELECT id FROM habits WHERE user_id = :user_id;  "
        ) is None

    def test_two_statements_rejected(self) -> None:
        result = SqlValidationService._check_single_statement(
            "SELECT 1; SELECT 2"
        )
        assert result is not None
        assert "Multiple statements" in result

    def test_statement_with_comment_terminator_ok(self) -> None:
        # The regex only looks at the raw SQL; comments are stripped upstream.
        # A semicolon followed only by whitespace is fine.
        assert SqlValidationService._check_single_statement(
            "SELECT id FROM habits\nWHERE user_id = :user_id;"
        ) is None


# ── SELECT-only check ─────────────────────────────────────────────────────────


class TestCheckSelectOnly:

    def test_select_ok(self) -> None:
        assert SqlValidationService._check_select_only(
            "SELECT id FROM habits WHERE user_id = :user_id"
        ) is None

    def test_update_rejected(self) -> None:
        result = SqlValidationService._check_select_only(
            "UPDATE habits SET name = 'x' WHERE id = 1"
        )
        assert result is not None

    def test_delete_rejected(self) -> None:
        result = SqlValidationService._check_select_only(
            "DELETE FROM habits WHERE id = 1"
        )
        assert result is not None

    def test_drop_rejected(self) -> None:
        result = SqlValidationService._check_select_only("DROP TABLE habits")
        assert result is not None

    def test_insert_rejected(self) -> None:
        result = SqlValidationService._check_select_only(
            "INSERT INTO habits VALUES (1)"
        )
        assert result is not None

    def test_select_with_where_ok(self) -> None:
        assert SqlValidationService._check_select_only(
            "SELECT * FROM habits WHERE user_id = :user_id LIMIT 10"
        ) is None


# ── Allowed-tables check ──────────────────────────────────────────────────────


class TestCheckAllowedTables:

    def test_known_table_ok(self) -> None:
        svc = _make_service(allowed=["habits"])
        assert svc._check_allowed_tables(
            "SELECT id FROM habits WHERE user_id = :user_id"
        ) is None

    def test_unknown_table_rejected(self) -> None:
        svc = _make_service(allowed=["habits"])
        result = svc._check_allowed_tables("SELECT id FROM secrets")
        assert result is not None
        assert "secrets" in result

    def test_join_known_table_ok(self) -> None:
        svc = _make_service(allowed=["habits", "habit_logs"])
        assert svc._check_allowed_tables(
            "SELECT h.id FROM habits h JOIN habit_logs hl ON h.id = hl.habit_id"
        ) is None

    def test_join_unknown_table_rejected(self) -> None:
        svc = _make_service(allowed=["habits"])
        result = svc._check_allowed_tables(
            "SELECT h.id FROM habits h JOIN passwords p ON h.id = p.id"
        )
        assert result is not None
        assert "passwords" in result

    def test_case_insensitive_match(self) -> None:
        svc = _make_service(allowed=["habits"])
        assert svc._check_allowed_tables(
            "SELECT id FROM HABITS WHERE user_id = :user_id"
        ) is None

    def test_multiple_unknown_tables_all_listed(self) -> None:
        svc = _make_service(allowed=["habits"])
        result = svc._check_allowed_tables(
            "SELECT * FROM secrets JOIN passwords ON secrets.id = passwords.id"
        )
        assert result is not None
        assert "secrets" in result
        assert "passwords" in result


# ── End-to-end validate() ─────────────────────────────────────────────────────


class TestValidate:

    def test_valid_query_returns_ok(self) -> None:
        svc = _make_service()
        result = svc.validate(
            "SELECT id, name FROM habits WHERE user_id = :user_id LIMIT 10"
        )
        assert result.status == ValidationStatus.OK
        assert result.rejection_reason is None

    def test_multiple_statements_returns_rejected(self) -> None:
        svc = _make_service()
        result = svc.validate("SELECT 1; SELECT 2")
        assert result.status == ValidationStatus.REJECTED
        assert result.rejection_reason is not None
        assert "Multiple statements" in result.rejection_reason

    def test_non_select_returns_rejected(self) -> None:
        svc = _make_service()
        result = svc.validate("DELETE FROM habits WHERE id = 1")
        assert result.status == ValidationStatus.REJECTED
        assert result.rejection_reason is not None

    def test_unknown_table_returns_rejected(self) -> None:
        svc = _make_service(allowed=["habits"])
        result = svc.validate(
            "SELECT id FROM admin_users WHERE user_id = :user_id"
        )
        assert result.status == ValidationStatus.REJECTED
        assert result.rejection_reason is not None
        assert "admin_users" in result.rejection_reason

    def test_returned_sql_matches_input(self) -> None:
        svc = _make_service()
        sql = "SELECT count(*) FROM habits WHERE user_id = :user_id"
        result = svc.validate(sql)
        assert result.sql == sql

    def test_never_raises_on_rejection(self) -> None:
        """validate() must return, not raise, for every rejection case."""
        svc = _make_service()
        # Should NOT raise
        result = svc.validate("DROP TABLE habits")
        assert result.status == ValidationStatus.REJECTED

    @pytest.mark.parametrize("sql,expected_status", [
        (
            "SELECT id FROM habits WHERE user_id = :user_id",
            ValidationStatus.OK,
        ),
        (
            "SELECT id FROM habits WHERE user_id = :user_id LIMIT 5",
            ValidationStatus.OK,
        ),
        (
            "SELECT id FROM habits WHERE user_id = :user_id;",
            ValidationStatus.OK,
        ),
        (
            "UPDATE habits SET name = 'x'",
            ValidationStatus.REJECTED,
        ),
        (
            "SELECT 1; DROP TABLE habits",
            ValidationStatus.REJECTED,
        ),
    ])
    def test_parametrized_cases(self, sql: str, expected_status: ValidationStatus) -> None:
        svc = _make_service()
        result = svc.validate(sql)
        assert result.status == expected_status

    def test_single_statement_checked_before_select(self) -> None:
        """Multiple-statement check fires before the SELECT check."""
        svc = _make_service()
        result = svc.validate("UPDATE habits SET name='x'; DELETE FROM habits")
        # Both are non-SELECT but the multiple-statement reason should appear.
        assert result.status == ValidationStatus.REJECTED
        assert "Multiple statements" in result.rejection_reason


# ── Module singleton ──────────────────────────────────────────────────────────


class TestSingleton:

    def test_singleton_is_accessible(self) -> None:
        assert sql_validation_service is not None

    def test_singleton_is_validation_service(self) -> None:
        assert isinstance(sql_validation_service, SqlValidationService)
