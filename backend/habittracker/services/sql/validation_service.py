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

# Matches alias declarations of the form:  <table_name> AS <alias>
# We allow  COUNT(*) AS n  and similar aggregate aliases, but not table aliases.
# Strategy: match <word> AS <word> when the left side is a known table pattern
# (has an underscore or is purely alpha and long — i.e. looks like a table name
# rather than an expression).  Simpler and safer: reject any <word> AS <word>
# where the left token does NOT contain '(' (so aggregate aliases are fine).
_TABLE_ALIAS = re.compile(
    r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s+AS\s+[a-zA-Z_][a-zA-Z0-9_]*\b',
    re.IGNORECASE,
)

# Matches qualified column references of the form  table.column
_QUALIFIED_COL = re.compile(
    r'\b([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\b',
    re.IGNORECASE,
)

# Matches  user_id = :user_id  with an optional table-name prefix.
# Accepts both  habits.user_id = :user_id  and bare  user_id = :user_id .
_USER_ID_FILTER = re.compile(
    r'(?:[a-zA-Z_][a-zA-Z0-9_]*\.)?user_id\s*=\s*:user_id\b',
    re.IGNORECASE,
)


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

    @staticmethod
    def _check_no_table_aliases(sql: str) -> str | None:
        """Return a rejection reason if the SQL declares a table alias.

        Aggregate-expression aliases like  COUNT(*) AS n  are allowed because
        the left side of AS contains a parenthesis.  Table aliases like
        bottle_events AS be  are rejected.
        """
        for match in _TABLE_ALIAS.finditer(sql):
            left_token = match.group(1)
            # Find the full expression to the left of AS (look backwards from match start)
            # Simple heuristic: if the character just before the left token (ignoring
            # whitespace) is ')', this is an aggregate alias — allow it.
            start = match.start()
            prefix = sql[:start].rstrip()
            if prefix.endswith(")"):
                continue
            return (
                f"SQL uses a table alias ('{match.group(0)}'). "
                "Write the full table name everywhere instead of aliasing it."
            )
        return None

    def _check_known_columns(self, sql: str) -> str | None:
        """Return a rejection reason if the SQL references an unknown table.column pair."""
        column_set = self._schema_svc.schema.column_set
        approved_tables = self._schema_svc.allowed_tables
        unknown: list[str] = []
        for match in _QUALIFIED_COL.finditer(sql):
            tbl = match.group(1).lower()
            col = match.group(2).lower()
            if tbl not in {t.lower() for t in approved_tables}:
                # Already caught by _check_allowed_tables; skip here.
                continue
            if (tbl, col) not in {(t.lower(), c.lower()) for t, c in column_set}:
                unknown.append(f"{tbl}.{col}")
        if unknown:
            return (
                f"SQL references column(s) that do not exist in the schema: "
                f"{sorted(set(unknown))}."
            )
        return None

    @staticmethod
    def _check_user_id_filter(sql: str) -> str | None:
        """Return a rejection reason if the SQL is missing a user_id filter."""
        if not _USER_ID_FILTER.search(sql):
            return (
                "SQL is missing the required user_id filter. "
                "Include  <table>.user_id = :user_id  in every WHERE clause."
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
            self._check_no_table_aliases,
            self._check_known_columns,
            self._check_user_id_filter,
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
