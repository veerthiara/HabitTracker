# Phase 09 Rev 02 — Safe SQL Execution Layer

## Goal

Build a controlled execution layer that accepts validated SQL text, enforces all safety rules, and returns structured rows. No LLM involved — this is the database-side guardrail.

## Key Decisions

- **Class-based service with config injection** — `SqlExecutionService(max_rows, timeout_ms)` takes configuration at construction time so tests can instantiate with `max_rows=5` without patching globals. Driven by feedback that all services must be class-based and configurable.

- **Helpers as class methods, not module-level functions** — `_validate_static()` and `_strip_sql_comments()` are `@staticmethod` on the class; `_apply_row_limit()` is an instance method (reads `self.max_rows`). Driven by feedback that logic belonging to a service should live inside its class.

- **Constants in `core/config.py`** — `SQL_MAX_ROWS` and `SQL_STATEMENT_TIMEOUT_MS` are read from env vars in `core/config.py`, not scattered as magic numbers in the service file. Consistent with how all other tuneable values are managed.

- **`services/sql/` subfolder** — moved `sql_schema_service.py` (from rev-01) and the new `execution_service.py` under `services/sql/`, matching the convention that each feature gets its own subfolder. Old top-level `sql_schema_service.py` deleted.

- **`services/sql/errors.py`** — `SqlError` base + `SqlExecutionError`, `ForbiddenStatementError`, `NonSelectStatementError` in a dedicated errors module rather than inside the service file. Consistent with the codebase convention for separating error types.

- **Copilot instructions rewritten** — replaced business-specific bullet points with a generalized `## Code conventions` section covering: project structure, class-based services, error handling, API vs internal schemas, constants/config, and testing. This is now a permanent reference for all future code generation.

## Architectural Context

```
services/sql/
  errors.py            ← SqlError base + all sql exception types
  schema_service.py    ← SqlSchemaService (rev-01, moved here)
  execution_service.py ← SqlExecutionService (rev-02, new)
```

`SqlExecutionService` sits between validation (rev-04) and generation (rev-03) in the pipeline. It is intentionally stateless except for its configuration — it never caches results or holds connection pools.

## Sequence

```
execute_sql request
    │
    ├─ _validate_static()  ← keyword + SELECT check (raises before any DB call)
    ├─ _apply_row_limit()  ← inject LIMIT if absent
    │
    └─ session.execute("SET LOCAL statement_timeout = :ms")
       session.execute(text(safe_sql), {"user_id": ...})
           │
           └─ SqlExecutionResult(columns, rows, row_count, sql)
```

## Scope Implemented

- `core/config.py` — `SQL_MAX_ROWS`, `SQL_STATEMENT_TIMEOUT_MS` (env-configurable)
- `services/sql/__init__.py` — subpackage marker
- `services/sql/errors.py` — `SqlError`, `SqlExecutionError`, `ForbiddenStatementError`, `NonSelectStatementError`
- `services/sql/execution_service.py` — `SqlExecutionService` class + `sql_execution_service` singleton
- `services/sql/schema_service.py` — `SqlSchemaService` fully class-based (builders moved into `@staticmethod` methods)
- `tests/habittracker/services/test_sql_execution_service.py` — 36 tests
- `Makefile` — fixed `test-embed` target path
- `.github/copilot-instructions.md` — rewritten Code conventions section

## Files Changed

```
backend/habittracker/core/config.py                        (modified)
backend/habittracker/services/sql/__init__.py              (new)
backend/habittracker/services/sql/errors.py                (new)
backend/habittracker/services/sql/execution_service.py     (new)
backend/habittracker/services/sql/schema_service.py        (new — replaces flat file)
backend/habittracker/services/sql_schema_service.py        (deleted)
backend/tests/habittracker/services/test_sql_execution_service.py (new)
backend/tests/habittracker/services/test_sql_schema_service.py    (modified — new imports)
.github/copilot-instructions.md                            (modified)
Makefile                                                   (modified)
```

## Notes

- 291 tests pass.
- `SET LOCAL statement_timeout` is scoped to the transaction — it resets automatically when the session closes. No cleanup needed.
- The forbidden keyword regex uses `\b` word boundaries so column names like `deleted_at` are not falsely flagged.

## Next Step

Rev 03 — SQL generation service: `SqlGenerationService` takes a natural-language question + `SchemaContext`, calls the LLM with a focused prompt, and returns a `SqlGenerationResult` containing the raw SQL text.
