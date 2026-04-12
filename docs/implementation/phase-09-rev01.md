# Phase 09 Rev 01 — SQL Analytics Schema + Pipeline Contracts

## Goal

Establish the schema layer and internal contracts for the SQL question-answering pipeline before any execution logic exists. The LLM must receive an accurate, complete picture of the database schema it is allowed to query.

## Key Decisions

- **ORM introspection instead of hardcoded schema** — `sql_schema_service.py` derives column names and types directly from `Model.__table__.columns`. This means adding or renaming a column in an ORM model automatically propagates to the schema prompt. The only manual entries are the things the ORM cannot provide: table-level descriptions, per-column business context, and the `exclude` set for internal columns.

- **`_TABLE_CONFIG` as the single approval gate** — only ORM classes that appear as keys in `_TABLE_CONFIG` are compiled into the schema. A model must be explicitly opted-in, preventing accidental exposure of new tables.

- **`schemas/` vs `services/` split** — Pydantic model definitions (`ColumnDef`, `TableDef`, `SchemaContext`, etc.) live in `schemas/sql_schema.py` and `schemas/sql_chat.py`, following the FastAPI convention that `schemas/` describes *what things are* and `services/` describes *what things do and what state they hold*.

- **Pipeline contracts defined up-front** (`sql_chat.py`) — `SqlGenerationRequest/Result`, `SqlValidationResult` + `ValidationStatus` enum, `SqlExecutionRequest/Result`, `SqlPipelineResult` are all declared now so rev-02 and rev-03 implement against a stable interface.

- **Tests guard `_TABLE_CONFIG` integrity** — four test classes with 30 parametrized cases catch phantom column descriptions, phantom excludes, and missing non-excluded ORM columns before they reach the LLM prompt.

## Architectural Context

```
sql_schema_service.py  ←  _TABLE_CONFIG (opt-in ORM classes + metadata)
        │
        ↓  introspects
ORM models (__table__.columns, __tablename__, col.foreign_keys)
        │
        ↓  builds
SchemaContext  →  to_prompt_string()  →  LLM system prompt (rev-02+)
                  allowed_tables      →  SQL validator (rev-02)
```

The `SchemaContext` is instantiated once at module load (`SCHEMA`, `ALLOWED_TABLES`). All downstream services import these module-level constants — nothing recomputes the schema per request.

## Flow

```
[Phase 09 pipeline — future revisions]

User question
    │
    ▼
SqlGenerationRequest  →  LLM (schema prompt from SCHEMA.to_prompt_string())
    │
    ▼
SqlGenerationResult (raw SQL)
    │
    ▼
SqlValidationResult (SELECT-only check, table allowlist)
    │
    ▼
SqlExecutionResult (columns, rows, row_count)
    │
    ▼
SqlPipelineResult (aggregated, returned to chat)
```

## Scope Implemented

- `schemas/sql_schema.py` — `ColumnDef`, `TableDef`, `ForeignKeyDef`, `SchemaContext` with `allowed_tables` property, `is_table_allowed()`, `to_prompt_string()`
- `schemas/sql_chat.py` — pipeline contracts: `SqlGenerationRequest/Result`, `ValidationStatus` enum, `SqlValidationResult`, `SqlExecutionRequest/Result`, `SqlPipelineResult`
- `services/sql_schema_service.py` — `_TABLE_CONFIG` (5 ORM classes), `_col_type_str()` type mapper, `_build_table_def()` / `_build_foreign_keys()` / `_build_schema()` builders, module-level `SCHEMA` + `ALLOWED_TABLES` constants, `get_schema_summary()` + `is_table_allowed()` public API
- `tests/habittracker/services/test_sql_schema_service.py` — 30 parametrized tests (4 classes)

## Files Changed

```
backend/habittracker/schemas/sql_schema.py          (new)
backend/habittracker/schemas/sql_chat.py            (new)
backend/habittracker/services/sql_schema_service.py (new)
backend/tests/habittracker/services/test_sql_schema_service.py (new)
```

## Notes

- `notes` table excludes `embedding` and `source` — vector columns are not useful for SQL analytics and would confuse the LLM.
- `users` table exposes only `id`, `created_at`, `updated_at` — no PII columns exist yet, but this is the right pattern to follow.
- All FK relationships are derived automatically from `col.foreign_keys` — no manual FK list to maintain.
- 255 tests pass (225 existing + 30 new).

## Next Step

Rev 02 — safe SQL execution layer: `sql_execution_service.py` accepts validated SQL, enforces SELECT-only at execution time, adds row limit + query timeout, returns `SqlExecutionResult`.
