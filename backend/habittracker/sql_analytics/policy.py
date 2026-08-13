"""SQL Policy Validation Service.

Reusable service that validates SQL execution policies:
- Bound parameter detection
- User/account scoping (Rev 04.3)

Result-bound enforcement is deferred beyond this revision.
"""

from __future__ import annotations

import sqlglot
from sqlglot import expressions as exp
from sqlglot.optimizer.scope import traverse_scope

from habittracker.sql_analytics.catalog import SqlCatalogProvider
from habittracker.sql_analytics.contracts import (
    SqlPolicyError,
    SqlPolicyValidationResult,
    SqlSchemaCatalog,
)
from habittracker.sql_analytics.settings import SqlAnalyticsSettings, get_settings


def _map_dialect(catalog_dialect: str) -> str | None:
    """Map catalog dialect name to SQLGlot dialect name."""
    mapping = {
        "postgresql": "postgres",
        "postgres": "postgres",
    }
    return mapping.get(catalog_dialect.lower())


def _extract_bound_parameters(stmt: exp.Expression) -> tuple[str, ...]:
    """Extract bind parameter names from the SQLGlot AST."""
    params: set[str] = set()

    for col in stmt.find_all(exp.Column):
        name = col.name
        if not name:
            continue
        if name.startswith("$") and name[1:].isdigit():
            params.add(name[1:])
        elif name == "?":
            params.add("?")
        elif name.startswith("@") and name[1:]:
            params.add(name[1:])

    return tuple(sorted(params))


def _is_bind_parameter(node: exp.Expression, required_param: str) -> bool:
    """Return True when the node is the required bind parameter."""
    if not isinstance(node, exp.Column):
        return False

    name = node.name
    if not name:
        return False
    if name.startswith("@"):
        return name[1:] == required_param
    if name.startswith("$") and name[1:].isdigit():
        return name[1:] == required_param
    if name == "?":
        return required_param == "?"
    return False


def _is_literal(node: exp.Expression) -> bool:
    """Return True when the node is a SQL literal."""
    return isinstance(node, exp.Literal)


def _get_visible_sources_in_scope(
    scope,
) -> dict[str, tuple[exp.Expression, exp.Expression | object]]:
    """Return all selected sources visible in a scope by local alias."""
    visible = {}
    for alias, (source_node, source_obj) in scope.selected_sources.items():
        visible[alias.lower()] = (source_node, source_obj)
    return visible


def _get_physical_sources_in_scope(scope) -> dict[str, tuple[exp.Expression, str]]:
    """Return only direct physical table reads from the scope."""
    physical = {}
    for alias, (source_node, source_obj) in _get_visible_sources_in_scope(scope).items():
        if isinstance(source_obj, exp.Table):
            physical[alias] = (source_node, source_obj.name.lower())
    return physical


class SqlPolicyValidationService:
    """Service that validates SQL execution policies."""

    def __init__(
        self,
        catalog_provider: SqlCatalogProvider,
        settings: SqlAnalyticsSettings | None = None,
    ) -> None:
        self._catalog_provider = catalog_provider
        self._settings = settings or get_settings()

    def validate(self, sql: str) -> SqlPolicyValidationResult:
        """Validate SQL against execution policies."""
        catalog = self._catalog_provider.get_catalog()
        dialect = _map_dialect(catalog.dialect)

        if dialect is None:
            return SqlPolicyValidationResult(
                valid=False,
                normalized_sql=None,
                errors=(SqlPolicyError(
                    code="UNSUPPORTED_DIALECT",
                    message=f"Unsupported catalog dialect: {catalog.dialect}",
                ),),
            )

        try:
            ast = sqlglot.parse(sql, read=dialect)
        except sqlglot.ParseError:
            return SqlPolicyValidationResult(
                valid=False,
                normalized_sql=None,
                errors=(SqlPolicyError(
                    code="PARSE_ERROR",
                    message="SQL could not be parsed",
                ),),
            )

        if len(ast) == 0 or ast[0] is None:
            return SqlPolicyValidationResult(
                valid=False,
                normalized_sql=None,
                errors=(SqlPolicyError(
                    code="EMPTY_SQL",
                    message="SQL must not be empty",
                ),),
            )

        if len(ast) > 1:
            return SqlPolicyValidationResult(
                valid=False,
                normalized_sql=None,
                errors=(SqlPolicyError(
                    code="MULTIPLE_STATEMENTS",
                    message="Multiple SQL statements are not allowed",
                ),),
            )

        stmt = ast[0]
        if not isinstance(stmt, (exp.Select, exp.With, exp.Union)):
            return SqlPolicyValidationResult(
                valid=False,
                normalized_sql=None,
                errors=(SqlPolicyError(
                    code="PARSE_ERROR",
                    message="SQL could not be parsed",
                ),),
            )

        normalized_sql = None
        try:
            normalized_sql = sqlglot.transpile(stmt.sql(), read=dialect, write=dialect)[0]
        except Exception:
            normalized_sql = None

        detected_parameters = _extract_bound_parameters(stmt)
        scope_errors, scoped_tables = self._validate_scopes(stmt, catalog)

        return SqlPolicyValidationResult(
            valid=len(scope_errors) == 0,
            normalized_sql=normalized_sql,
            scoped_tables=tuple(sorted(scoped_tables)),
            detected_parameters=detected_parameters,
            effective_limit=None,
            errors=tuple(scope_errors),
            warnings=(),
        )

    def _validate_scopes(
        self,
        stmt: exp.Expression,
        catalog: SqlSchemaCatalog,
    ) -> tuple[list[SqlPolicyError], set[str]]:
        """Validate every SQLGlot scope for direct physical reads."""
        errors: list[SqlPolicyError] = []
        scoped_tables: set[str] = set()

        try:
            scopes = list(traverse_scope(stmt))
        except Exception as exc:
            errors.append(SqlPolicyError(
                code="UNSUPPORTED_SQL_FEATURE",
                message=f"Scope analysis failed: {type(exc).__name__}",
            ))
            return errors, scoped_tables

        for scope in scopes:
            physical_sources = _get_physical_sources_in_scope(scope)
            direct_physical_source_count = len(physical_sources)

            for alias, (_, physical_name) in physical_sources.items():
                if physical_name not in catalog.allowed_table_names():
                    continue

                table_def = catalog.get_table(physical_name)
                if not table_def.user_scoped:
                    continue
                if table_def.scope_strategy != "direct":
                    errors.append(SqlPolicyError(
                        code="USER_SCOPE_UNSUPPORTED",
                        message=f"Table '{physical_name}' has unsupported scope strategy: {table_def.scope_strategy}",
                        context=physical_name,
                    ))
                    continue

                user_scope_cols = {col.name.lower() for col in table_def.user_scope_columns()}
                if not user_scope_cols:
                    continue

                scope_proven, error_code = self._check_scope_predicates(
                    scope=scope,
                    table_name=physical_name,
                    table_alias=alias,
                    user_scope_cols=user_scope_cols,
                    direct_physical_source_count=direct_physical_source_count,
                )
                if not scope_proven:
                    if error_code == "USER_SCOPE_AMBIGUOUS":
                        message = f"Table '{physical_name}' scope predicate contains unsafe boolean logic (OR)"
                    elif error_code == "USER_SCOPE_LITERAL_NOT_ALLOWED":
                        message = f"Table '{physical_name}' uses literal value instead of bind parameter for user scope"
                    elif error_code == "USER_SCOPE_PARAMETER_REQUIRED":
                        message = f"Table '{physical_name}' requires the @{self._settings.required_scope_parameter} parameter for user scope"
                    else:
                        message = (
                            f"User-scoped table '{physical_name}' requires a predicate on a user-scope "
                            f"column against @{self._settings.required_scope_parameter}"
                        )
                    errors.append(SqlPolicyError(
                        code=error_code,
                        message=message,
                        context=physical_name,
                    ))
                    continue

                scoped_tables.add(physical_name)

        return errors, scoped_tables

    def _check_scope_predicates(
        self,
        scope,
        table_name: str,
        table_alias: str,
        user_scope_cols: set[str],
        direct_physical_source_count: int,
    ) -> tuple[bool, str]:
        """Check whether the scope contains a valid user-scope predicate."""
        if not isinstance(scope.expression, exp.Select):
            return False, "USER_SCOPE_REQUIRED"

        where = scope.expression.args.get("where")
        if where is None:
            return False, "USER_SCOPE_REQUIRED"

        predicates = self._flatten_boolean(where.this)
        if self._has_unsafe_or(predicates):
            return False, "USER_SCOPE_AMBIGUOUS"

        required_param = self._settings.required_scope_parameter

        for predicate in predicates:
            if not isinstance(predicate, exp.EQ):
                continue

            for col_side, param_side in ((predicate.left, predicate.right), (predicate.right, predicate.left)):
                if not isinstance(col_side, exp.Column):
                    continue

                col_name = col_side.name.lower()
                if col_name not in user_scope_cols:
                    continue

                if col_side.table:
                    qualifier = col_side.table.this if hasattr(col_side.table, "this") else str(col_side.table)
                    if qualifier.lower() != table_alias:
                        continue
                elif direct_physical_source_count > 1:
                    continue

                if _is_bind_parameter(param_side, required_param):
                    return True, ""

                if isinstance(param_side, exp.Column):
                    param_name = param_side.name
                    if param_name and param_name.startswith("@") and param_name[1:] != required_param:
                        return False, "USER_SCOPE_PARAMETER_REQUIRED"
                    if param_name and param_name.startswith("$") and param_name[1:] != required_param:
                        return False, "USER_SCOPE_PARAMETER_REQUIRED"
                    if param_name == "?" and required_param != "?":
                        return False, "USER_SCOPE_PARAMETER_REQUIRED"

                if _is_literal(param_side):
                    return False, "USER_SCOPE_LITERAL_NOT_ALLOWED"

        return False, "USER_SCOPE_REQUIRED"

    def _flatten_boolean(self, expr: exp.Expression) -> list[exp.Expression]:
        """Flatten nested AND expressions and preserve OR expressions as units."""
        if isinstance(expr, exp.And):
            predicates = []
            if expr.this:
                predicates.extend(self._flatten_boolean(expr.this))
            right = expr.args.get("expression")
            if right:
                predicates.extend(self._flatten_boolean(right))
            return predicates
        if isinstance(expr, exp.Or):
            return [expr]
        return [expr]

    def _has_unsafe_or(self, predicates: list[exp.Expression]) -> bool:
        """Return True when any predicate contains OR logic."""
        return any(isinstance(predicate, exp.Or) for predicate in predicates)
