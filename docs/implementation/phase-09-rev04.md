# Phase 09 Rev 04 — SQL Validation + End-to-End Pipeline Service

## Goal

Add `SqlValidationService` (static safety checks on generated SQL) and `SqlPipelineService` (orchestrates generation → validation → execution into a single call), completing the full text-to-SQL pipeline.

## Key Decisions

- **`SqlValidationService.validate()` accepts raw SQL rather than `SqlGenerationResult`** — this keeps the validation contract free from the generation schema and makes the validator reusable in any context (e.g. a future API that accepts user-provided SQL).
- **Reuse `SqlExecutionService._validate_static()`** for the SELECT/forbidden-keyword check instead of duplicating the same regex. This guarantees both services apply exactly the same rules and there is a single place to update.
- **Return `SqlValidationResult` rather than raise** — the validation service encodes rejections in a result object so the pipeline (and future callers) can handle them without a try/except at every call site. Only truly unexpected errors would propagate as exceptions.
- **`SqlPipelineService.run()` never raises** — all three failure modes (generation error, validation rejection, execution error) are caught and returned as `SqlPipelineResult(success=False)`. The chat layer can call `run()` and inspect `result.success` without defensive exception handling.
- **Order of validation checks**: (1) multiple-statement detection, (2) SELECT/forbidden-keyword check, (3) allowed-tables check. Multiple-statement check is first because it is the cheapest and most obviously dangerous.
- **Allowed-tables check is case-insensitive** — SQL identifiers are case-insensitive in Postgres; normalising to lowercase prevents false positives (`HABITS` vs `habits`).

## Architectural Context

Rev 04 closes the `services/sql/` pipeline layer. The three services now form a directed pipeline:

```
SqlGenerationService   →  produces SqlGenerationResult
         ↓
SqlValidationService   →  produces SqlValidationResult (OK or REJECTED)
         ↓ (only if OK)
SqlExecutionService    →  produces SqlExecutionResult
         ↓
SqlPipelineService     →  assembles SqlPipelineResult (chat layer entry point)
```

`SqlPipelineService` is the only export that the chat/LangGraph layer will consume. Future revisions that add LangGraph routing will call `sql_pipeline_service.run(request, session)` and receive a fully-typed result regardless of which stage failed.

## Sequence Diagram

```
ChatLayer
    │
    ▼ run(request, session)
SqlPipelineService
    │
    ├── generation_svc.generate(request)
    │       SqlGenerationError ──────────────────────► SqlPipelineResult(success=False)
    │
    ├── validation_svc.validate(sql)
    │       status=REJECTED ──────────────────────────► SqlPipelineResult(success=False)
    │
    └── execution_svc.execute(exec_request, session)
            SqlExecutionError ───────────────────────► SqlPipelineResult(success=False)
            success ─────────────────────────────────► SqlPipelineResult(success=True)
```

## Scope Implemented

- `SqlValidationService` with three static-analysis checks: multi-statement, SELECT-only, allowed-tables
- `sql_validation_service` module-level singleton
- `SqlPipelineService` orchestrating all three stages with safe fallback on any failure
- `sql_pipeline_service` module-level singleton wired to production services
- `SqlValidationError` added to `errors.py` (groundwork for future pipeline-level exception surfacing)
- 55 unit tests (27 for validation, 28 for pipeline); all 370 tests green

## Files Changed

```
backend/habittracker/services/sql/validation_service.py   ← new
backend/habittracker/services/sql/pipeline_service.py     ← new
backend/habittracker/services/sql/errors.py               ← SqlValidationError added
backend/tests/habittracker/services/sql/test_sql_validation_service.py  ← new
backend/tests/habittracker/services/sql/test_sql_pipeline_service.py    ← new
docs/implementation/phase-09-rev04.md                     ← this file
```

## Notes

- `SqlPipelineService` accepts raw `SqlGenerationRequest` (question + user_id) and a SQLAlchemy `Session`. The chat layer does not need to know about intermediate schemas.
- The allowed-tables regex (`FROM`/`JOIN` extraction) handles quoted identifiers and is case-insensitive. CTE and subquery table aliases are not extracted as table references, which is the desired behaviour.
- `SqlValidationService` is a class (not just module functions) so tests can inject a custom `SqlSchemaService` with a controlled approved-tables list without patching module globals.

## Next Step

Rev 05 — wire `SqlPipelineService` into the chat path: route SQL-intent questions through the pipeline, format the `SqlExecutionResult` as a natural-language answer using the LLM, and return it via `ChatResponse`.
