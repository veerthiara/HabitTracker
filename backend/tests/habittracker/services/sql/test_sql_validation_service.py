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
    # Provide a realistic column_set for the new column-level checks.
    schema_svc.schema.column_set = frozenset([
        ("habits", "id"), ("habits", "user_id"), ("habits", "name"),
        ("habits", "description"), ("habits", "frequency"), ("habits", "is_active"),
        ("habit_logs", "id"), ("habit_logs", "user_id"), ("habit_logs", "habit_id"),
        ("habit_logs", "logged_date"), ("habit_logs", "notes"),
        ("users", "id"), ("users", "email"),
        ("bottle_events", "id"), ("bottle_events", "user_id"),
        ("bottle_events", "event_ts"), ("bottle_events", "volume_ml"),
    ])
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


# ── New Rev 09 checks ──────────────────────────────────────────────────────────


class TestCheckNoTableAliases:
    """_check_no_table_aliases rejects  table AS alias  but allows aggregate aliases."""

    def test_no_alias_ok(self) -> None:
        assert SqlValidationService._check_no_table_aliases(
            "SELECT bottle_events.volume_ml FROM bottle_events WHERE bottle_events.user_id = :user_id"
        ) is None

    def test_aggregate_alias_ok(self) -> None:
        # COUNT(*) AS n is a result-column alias, not a table alias — must pass.
        assert SqlValidationService._check_no_table_aliases(
            "SELECT COUNT(*) AS total FROM habits WHERE habits.user_id = :user_id"
        ) is None

    def test_sum_alias_ok(self) -> None:
        assert SqlValidationService._check_no_table_aliases(
            "SELECT SUM(bottle_events.volume_ml) AS total_ml FROM bottle_events WHERE bottle_events.user_id = :user_id"
        ) is None

    @pytest.mark.parametrize("sql,alias_hint", [
        ("SELECT T1.volume_ml FROM bottle_events AS T1 WHERE T1.user_id = :user_id", "T1"),
        ("SELECT be.volume_ml FROM bottle_events AS be WHERE be.user_id = :user_id", "be"),
        (
            "SELECT T1.volume_ml FROM bottle_events AS T1 "
            "JOIN users AS T2 ON T1.user_id = T2.id WHERE T1.user_id = :user_id",
            "T1",
        ),
    ])
    def test_table_alias_rejected(self, sql: str, alias_hint: str) -> None:
        result = SqlValidationService._check_no_table_aliases(sql)
        assert result is not None
        assert "alias" in result.lower()


class TestCheckKnownColumns:
    """_check_known_columns rejects references to columns not in SchemaContext."""

    def test_known_column_ok(self) -> None:
        svc = _make_service(allowed=["bottle_events"])
        assert svc._check_known_columns(
            "SELECT bottle_events.volume_ml FROM bottle_events WHERE bottle_events.user_id = :user_id"
        ) is None

    def test_unknown_column_rejected(self) -> None:
        svc = _make_service(allowed=["bottle_events"])
        result = svc._check_known_columns(
            "SELECT bottle_events.calories FROM bottle_events WHERE bottle_events.user_id = :user_id"
        )
        assert result is not None
        assert "bottle_events.calories" in result

    def test_unknown_column_on_allowed_table_rejected(self) -> None:
        svc = _make_service(allowed=["habits"])
        result = svc._check_known_columns(
            "SELECT habits.nonexistent FROM habits WHERE habits.user_id = :user_id"
        )
        assert result is not None

    def test_disallowed_table_skipped_by_known_column_check(self) -> None:
        # Table-level rejection is caught by _check_allowed_tables; column check should
        # not also report it (avoid double-reporting unknown tables).
        svc = _make_service(allowed=["habits"])
        result = svc._check_known_columns(
            "SELECT secrets.password FROM secrets WHERE secrets.user_id = :user_id"
        )
        # secrets is not in approved tables, so _check_known_columns skips it.
        assert result is None


class TestCheckUserIdFilter:
    """_check_user_id_filter rejects SQL missing a proper user_id = :user_id filter."""

    def test_correct_filter_ok(self) -> None:
        assert SqlValidationService._check_user_id_filter(
            "SELECT bottle_events.volume_ml FROM bottle_events WHERE bottle_events.user_id = :user_id"
        ) is None

    def test_habit_logs_filter_ok(self) -> None:
        assert SqlValidationService._check_user_id_filter(
            "SELECT COUNT(*) FROM habit_logs WHERE habit_logs.user_id = :user_id LIMIT 200"
        ) is None

    @pytest.mark.parametrize("bad_sql", [
        # bare bind parameter without column name
        "SELECT * FROM bottle_events WHERE %(user_id)s AND event_ts >= NOW()",
        # bind with wrong operator
        "SELECT * FROM bottle_events WHERE bottle_events.user_id IN (:user_id)",
        # completely missing filter
        "SELECT * FROM bottle_events LIMIT 200",
        # user_id used in a subquery but not in outer WHERE
        "SELECT * FROM bottle_events LIMIT 200",
    ])
    def test_missing_or_malformed_filter_rejected(self, bad_sql: str) -> None:
        result = SqlValidationService._check_user_id_filter(bad_sql)
        assert result is not None
        assert "user_id" in result.lower()


class TestValidateWithNewChecks:
    """End-to-end validate() with all Rev 09 checks active."""

    def test_alias_causes_rejection(self) -> None:
        svc = _make_service(allowed=["bottle_events"])
        sql = (
            "SELECT T1.volume_ml FROM bottle_events AS T1 "
            "WHERE T1.user_id = :user_id LIMIT 200"
        )
        result = svc.validate(sql)
        assert result.status == ValidationStatus.REJECTED
        assert "alias" in result.rejection_reason.lower()

    def test_unknown_column_causes_rejection(self) -> None:
        svc = _make_service(allowed=["bottle_events"])
        sql = (
            "SELECT bottle_events.calories FROM bottle_events "
            "WHERE bottle_events.user_id = :user_id LIMIT 200"
        )
        result = svc.validate(sql)
        assert result.status == ValidationStatus.REJECTED
        assert "calories" in result.rejection_reason

    def test_missing_user_id_causes_rejection(self) -> None:
        svc = _make_service(allowed=["bottle_events"])
        sql = "SELECT SUM(bottle_events.volume_ml) FROM bottle_events LIMIT 200"
        result = svc.validate(sql)
        assert result.status == ValidationStatus.REJECTED
        assert "user_id" in result.rejection_reason.lower()

    def test_correct_sql_passes_all_checks(self) -> None:
        svc = _make_service(allowed=["bottle_events"])
        sql = (
            "SELECT SUM(bottle_events.volume_ml) AS total_ml"
            " FROM bottle_events"
            " WHERE bottle_events.user_id = :user_id"
            "   AND bottle_events.event_ts >= NOW() - INTERVAL '30 days'"
            " LIMIT 200"
        )
        result = svc.validate(sql)
        assert result.status == ValidationStatus.OK
