"""SQL Validation Exceptions.

Exceptions for SQL validation layer.
"""

from __future__ import annotations


class SqlValidationException(RuntimeError):
    """Base exception for unexpected SQL validation failures.

    This represents an unexpected validator failure, not an expected
    validation failure (which should be represented through
    SqlValidationResult with valid=False).
    """


class SqlParseError(SqlValidationException):
    """Raised internally when SQL cannot be parsed by the underlying parser."""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        if cause is not None:
            self.__cause__ = cause