"""SQL validation service — SqlValidationService.

SqlValidationService performs static safety checks on generated SQL
before it is handed to the execution layer.

Checks performed (in order):
  1. No multiple statements — a semicolon separating two statements
     is rejected. A trailing semicolon is allowed.
  2. SELECT-only — the statement must start with SELECT after comment
     stripping (delegates to SqlExecutionService._validate_static so
     the exact same keyword guard and SELECT check is applied in both
     places without duplication).
  3. Allowed-tables check — every table referenced in the SQL must be
     in the approved set from SqlSchemaService.allowed_tables.

Design:
  - All checks are @staticmethod or instance methods on the class.
  - Returns SqlValidationResult (OK or REJECTED with a reason) rather
    than raising, so the pipeline can decide how to handle a rejection
    without a try/except at every call site.
  - sql_validation_service is the module-level singleton.
"""

from __future__ import annotations

import re

from habittracker.schemas.sql_chat import SqlValidationResult, ValidationStatus
from habittracker.services.sql.errors import ForbiddenStatementError, NonSelectStatementError
from habittracker.services.sql.execution_service import SqlExecutionService
from habittracker.services.sql.schema_service import SqlSchemaService, sql_schema_service

# Matches a table name that follows FROM, JOIN, or a comma in the FROM clause.
# Captures bare identifiers and double-quoted identifiers.
_TABLE_REF = re.compile(
    r'\b(?:FROM|JOIN)\s+"?([a-zA-Z_][a-zA-Z0-9_]*)"?',
    re.IGNORECASE,
)

# Detects a semicolon that is NOT at the very end of the trimmed statement.
_MULTIPLE_STATEMENTS = re.compile(r";.+", re.DOTALL)


class SqlValidationService:
    """Validates generated SQL against safety rules before execution.

    Injecting the schema service at construction time lets tests pass a
    custom approved-tables set without patching module globals.
    """

    def __init__(self, schema_svc: SqlSchemaService) -> None:
        self._schema_svc = schema_svc

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _check_single_statement(sql: str) -> str | None:
        """Return a rejection reason if the SQL contains multiple statements."""
        stripped = sql.rstrip().rstrip(";")
        if _MULTIPLE_STATEMENTS.search(stripped):
            return "Multiple statements are not permitted. Only a single SELECT is allowed."
        return None

    @staticmethod
    def _check_select_only(sql: str) -> str | None:
        """Return a rejection reason if the SQL is not a safe SELECT."""
        try:
            SqlExecutionService._validate_static(sql)
        except (ForbiddenStatementError, NonSelectStatementError) as exc:
            return str(exc)
        return None

    def _check_allowed_tables(self, sql: str) -> str | None:
        """Return a rejection reason if the SQL references a disallowed table."""
        approved = self._schema_svc.allowed_tables
        found = {m.group(1).lower() for m in _TABLE_REF.finditer(sql)}
        disallowed = found - {t.lower() for t in approved}
        if disallowed:
            return (
                f"SQL references table(s) not in the approved list: "
                f"{sorted(disallowed)}. Approved: {sorted(approved)}."
            )
        return None

    # ── Public API ────────────────────────────────────────────────────────────

    def validate(self, sql: str) -> SqlValidationResult:
        """Run all static checks and return a SqlValidationResult.

        Never raises — rejections are encoded in the result's status and
        rejection_reason fields so the pipeline can handle them gracefully.
        """
        for check in (
            self._check_single_statement,
            self._check_select_only,
            self._check_allowed_tables,
        ):
            reason = check(sql)
            if reason:
                return SqlValidationResult(
                    status=ValidationStatus.REJECTED,
                    sql=sql,
                    rejection_reason=reason,
                )
        return SqlValidationResult(status=ValidationStatus.OK, sql=sql)


# ── Module-level singleton ────────────────────────────────────────────────────

sql_validation_service = SqlValidationService(schema_svc=sql_schema_service)
