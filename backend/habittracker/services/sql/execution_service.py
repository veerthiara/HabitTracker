"""SQL execution service — SqlExecutionService.

SqlExecutionService executes validated, read-only SQL against the
application database.

Design:
  - All validation and transformation helpers are private methods of the
    class. Static helpers have no instance state dependency; the row-limit
    helper is an instance method because it reads self.max_rows.
  - SqlExecutionService takes configuration at construction time
    (max_rows, timeout_ms) so tests can override values without patching.
  - sql_execution_service is the module-level singleton for production use.
    Callers import the instance, not the class.

Safety guarantees:
  1. Static keyword guard — rejects forbidden write/DDL keywords before
     touching the database.
  2. SELECT enforcement — only statements that start with SELECT (after
     stripping comments) are allowed.
  3. Row cap — LIMIT is appended automatically when absent.
  4. Statement timeout — SET LOCAL statement_timeout is applied per query.
  5. Bind parameter injection — user_id is injected as :user_id, never
     interpolated into the SQL string.
"""

from __future__ import annotations

import logging
import re

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from habittracker.core.config import SQL_MAX_ROWS, SQL_STATEMENT_TIMEOUT_MS
from habittracker.schemas.sql_chat import SqlExecutionRequest, SqlExecutionResult
from habittracker.services.sql.errors import (
    ForbiddenStatementError,
    NonSelectStatementError,
    SqlExecutionError,
)

logger = logging.getLogger(__name__)

# ── Compiled patterns ─────────────────────────────────────────────────────────

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)
_HAS_LIMIT = re.compile(r"\bLIMIT\s+\d+", re.IGNORECASE)
_STARTS_SELECT = re.compile(r"^\s*SELECT\b", re.IGNORECASE)


# ── Service class ─────────────────────────────────────────────────────────────


class SqlExecutionService:
    """Executes validated, read-only SQL analytics queries against the database.

    Configuration is injected at construction time so tests can instantiate
    the service with a small row cap or short timeout without patching globals.
    """

    def __init__(
        self,
        max_rows: int = SQL_MAX_ROWS,
        timeout_ms: int = SQL_STATEMENT_TIMEOUT_MS,
    ) -> None:
        self.max_rows = max_rows
        self.timeout_ms = timeout_ms

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _strip_sql_comments(sql: str) -> str:
        """Remove single-line (--) and block (/* */) SQL comments."""
        sql = re.sub(r"--[^\n]*", "", sql)
        sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
        return sql.strip()

    @staticmethod
    def _validate_static(sql: str) -> None:
        """Raise if the SQL contains forbidden keywords or is not a SELECT.

        Raises:
            ForbiddenStatementError: a write/DDL keyword is present.
            NonSelectStatementError: the statement does not begin with SELECT.
        """
        match = _FORBIDDEN.search(sql)
        if match:
            raise ForbiddenStatementError(
                f"Forbidden keyword '{match.group()}' found in SQL."
            )
        stripped = SqlExecutionService._strip_sql_comments(sql)
        if not _STARTS_SELECT.match(stripped):
            raise NonSelectStatementError(
                "Only SELECT statements are permitted. "
                f"Statement begins with: {stripped[:60]!r}"
            )

    def _apply_row_limit(self, sql: str) -> str:
        """Append LIMIT if no LIMIT clause is present, using self.max_rows."""
        if _HAS_LIMIT.search(sql):
            return sql
        return f"{sql.rstrip().rstrip(';')}\nLIMIT {self.max_rows}"

    # ── Public API ────────────────────────────────────────────────────────────

    def execute(
        self,
        request: SqlExecutionRequest,
        session: Session,
    ) -> SqlExecutionResult:
        """Execute a pre-validated SELECT statement and return structured rows.

        Args:
            request: Contains `sql` (the statement) and `user_id` (bind param).
            session: Active SQLAlchemy Session from the request context.

        Returns:
            SqlExecutionResult with columns, rows, and row_count.

        Raises:
            ForbiddenStatementError: SQL contains a write/DDL keyword.
            NonSelectStatementError: SQL does not start with SELECT.
            SqlExecutionError: Any database-level failure during execution.
        """
        self._validate_static(request.sql)
        safe_sql = self._apply_row_limit(request.sql)

        logger.debug("Executing analytics SQL: %s", safe_sql)

        try:
            session.execute(
                text("SET LOCAL statement_timeout = :ms"),
                {"ms": self.timeout_ms},
            )
            result = session.execute(
                text(safe_sql),
                {"user_id": request.user_id},
            )
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            return SqlExecutionResult(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                sql=safe_sql,
            )
        except SQLAlchemyError as exc:
            logger.warning("SQL execution failed: %s", exc)
            raise SqlExecutionError(str(exc)) from exc


# ── Module-level singleton ────────────────────────────────────────────────────
# Callers import this instance, not the class.

sql_execution_service = SqlExecutionService()

