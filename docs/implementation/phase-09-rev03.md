# Phase 09 Rev 03 — SQL Generation Service

## Goal

Translate a natural-language analytical question into a safe, parameterised SELECT statement using the local LLM, using the approved SchemaContext as the only source of table/column truth.

## Key Decisions

- **Prompt encapsulated entirely inside the service** — all prompt text lives in `generation_service.py`. Nothing leaks into callers, schemas, or config. This makes prompt iteration a single-file change.

- **UNSUPPORTED escape hatch** — the system prompt instructs the LLM to output the literal string `UNSUPPORTED` when the question cannot be answered with the schema. `_extract_sql()` detects this and raises `SqlGenerationError` rather than forwarding a nonsense query downstream.

- **Markdown fence stripping** — `_extract_sql()` handles both bare SQL and `\`\`\`sql ... \`\`\`` fences. LLMs frequently wrap output in code fences despite being told not to; stripping them here keeps the downstream pipeline clean.

- **Error wrapped as `SqlGenerationError`** — `ChatCompletionError` from the provider is caught and re-raised as `SqlGenerationError` so callers only need to handle the SQL feature's own error hierarchy.

- **Test subfolder mirrors source** — tests live under `tests/habittracker/services/sql/` matching `services/sql/`, consistent with the project convention.

- **`SqlGenerationError` added to `errors.py`** — all SQL feature exceptions stay in one place.

## Architectural Context

```
services/sql/
  errors.py              ← + SqlGenerationError
  schema_service.py      ← provides get_summary() to the prompt builder
  generation_service.py  ← SqlGenerationService (rev-03, new)
  execution_service.py   ← SqlExecutionService (rev-02)
```

## Sequence

```
SqlGenerationRequest(question, user_id)
    │
    ├─ _build_system_prompt(schema_summary)
    │      schema_svc.get_summary() → injects schema into prompt template
    │
    └─ provider.complete([system, user])
           │
           ├─ ChatCompletionError → SqlGenerationError
           │
           └─ raw LLM response
                  │
                  ├─ _extract_sql(): strip fences, detect UNSUPPORTED
                  │
                  └─ SqlGenerationResult(sql, question, user_id)
```

## Scope Implemented

- `services/sql/errors.py` — added `SqlGenerationError`
- `services/sql/generation_service.py` — `SqlGenerationService` class + `sql_generation_service` singleton
- `tests/habittracker/services/sql/__init__.py` — test subpackage
- `tests/habittracker/services/sql/test_sql_generation_service.py` — 24 tests

## Files Changed

```
backend/habittracker/services/sql/errors.py                       (modified)
backend/habittracker/services/sql/generation_service.py           (new)
backend/tests/habittracker/services/sql/__init__.py               (new)
backend/tests/habittracker/services/sql/test_sql_generation_service.py (new)
```

## Notes

- 315 tests pass (291 from rev-02 + 24 new).
- The singleton wires to `OllamaChatProvider()` and `sql_schema_service` at import time. In production nothing needs to be configured — both singletons already exist.
- The generation service performs no static SQL validation itself. That is the responsibility of rev-04 (SqlValidationService), which runs after generation.

## Next Step

Rev 04 — SQL validation + end-to-end pipeline: `SqlValidationService` checks the generated SQL against the allowed table list and SELECT-only rules, then wires generation → validation → execution into a single `SqlPipelineService` that returns `SqlPipelineResult`.
