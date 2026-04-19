"""SQL analytics path — exception hierarchy.

All SQL-path exceptions derive from SqlError so callers can catch the
entire family with a single except clause when needed.

Keeping errors in a dedicated module means any service (execution,
validation, generation) can import them without importing the service
that raises them, avoiding circular dependencies.
"""

from __future__ import annotations


class SqlError(Exception):
    """Base class for all SQL analytics errors."""


class SqlExecutionError(SqlError):
    """Raised when SQL execution fails at the database level."""


class ForbiddenStatementError(SqlError):
    """Raised when the SQL contains a forbidden write or DDL keyword."""


class NonSelectStatementError(SqlError):
    """Raised when the statement does not begin with SELECT."""


class SqlGenerationError(SqlError):
    """Raised when the LLM fails to produce a usable SQL statement."""


class SqlValidationError(SqlError):
    """Raised when generated SQL fails pre-execution validation checks."""


class SqlAnswerError(SqlError):
    """Raised when the LLM fails to produce an answer from the SQL results."""


class SqlTemplateError(SqlError):
    """Raised when no fixed SQL template exists for the given intent."""


class SqlParameterExtractionError(SqlError):
    """Raised when the LLM fails to extract structured parameters from the question."""


class SqlRepairError(SqlError):
    """Raised when the repair LLM call fails or produces unusable SQL."""
