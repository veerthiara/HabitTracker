# Phase 09 Rev 10 — One-Pass SQL Repair Loop

## Goal

Recover safely from predictable SQL mistakes at execution time. When the generated SQL fails with a Postgres error, attempt a single LLM-assisted repair before returning a fallback to the user. Users never see a raw database error.

## Key Decisions

- **One repair attempt, no more** — prevents runaway LLM retry spirals and keeps latency bounded. A second failure after repair returns a safe fallback message ("I wasn't able to answer that question reliably — please try rephrasing.").

- **Repaired SQL passes the full validation pipeline before retry** — the repair loop does not bypass alias blocking, column existence, or user_id filter checks. If the repaired SQL is invalid, the repair is abandoned immediately rather than executing a potentially unsafe query.

- **`SqlRepairService` is a separate class, not a method on `SqlGenerationService`** — the context is different (schema + failed SQL + DB error, not a user question alone), and the failure mode is different (`SqlRepairError` vs `SqlGenerationError`). Keeping them separate avoids coupling and makes each independently testable.

- **Pipeline result carries `repair_attempted` and `repair_error` fields** — callers and observability tooling (Langfuse) can see whether a repair was triggered and why it succeeded or failed, without changing the public chat API shape.

- **Both attempts logged at WARNING level** — the original SQL, the DB error, and the repaired SQL are each logged so that recurring failures are visible in Langfuse without re-running the query manually.

## Architectural Context

The repair loop is contained entirely within a new `_execute_with_repair()` helper in `SqlPipelineService`. The four pipeline stages (generate → validate → execute → answer) are unchanged; repair is an internal retry inside the execute stage.

```
generate SQL
     │
validate SQL ── REJECTED ──────────────────────► return failure
     │
execute SQL ── success ─────────────────────────► answer generation
     │
     └─ SqlExecutionError
             │
        SqlRepairService.repair(question, failed_sql, db_error)
             │
             ├─ SqlRepairError  ──────────────────► return failure (repair_attempted=True)
             │
        re-validate repaired SQL ── REJECTED ────► return failure (repair_attempted=True)
             │
        retry execute
             │
             ├─ SqlExecutionError ───────────────► return failure (repair_attempted=True)
             │
             └─ success ────────────────────────► answer generation (repair_attempted=True)
```

## Scope Implemented

- `SqlRepairService`: constructs a repair prompt from schema + failed SQL + DB error; strips markdown fences; raises `SqlRepairError` on empty response, `UNSUPPORTED` signal, or LLM failure
- `SqlRepairError`: new exception class in `services/sql/errors.py`, inheriting from `SqlError`
- `SqlPipelineService._execute_with_repair()`: orchestrates the one-pass loop; returns `(execution_result | None, repair_attempted, repair_error_str | None)`
- `SqlPipelineResult` fields added: `repair_attempted: bool` (default `False`), `repair_error: str | None` (default `None`)
- `sql_repair_service` singleton wired into `sql_pipeline_service` singleton at module level

## Files Changed

```
backend/habittracker/services/sql/repair_service.py                       (new)
backend/habittracker/services/sql/errors.py                               (SqlRepairError)
backend/habittracker/services/sql/pipeline_service.py                     (_execute_with_repair, repair_svc param)
backend/habittracker/schemas/sql_chat.py                                  (repair_attempted, repair_error fields)
backend/tests/habittracker/services/sql/test_sql_repair_service.py        (new — 17 tests)
backend/tests/habittracker/services/sql/test_sql_pipeline_service.py      (TestRepairLoop — 9 tests)
```

## Notes

- The repair prompt mirrors the generation prompt rules: no aliases, explicit user_id filter pattern, SELECT only, LIMIT required.
- Repair is triggered only by `SqlExecutionError`, not by validation failures. Validation failures are already structured errors; the repair prompt would have no DB error to reason from.
- 539 tests passing after this revision (521 from Rev 08-09 + 18 new).

## Next Step

Rev 11 — Evaluation set and regression harness: fixture file with 20+ questions, expected intents, expected tables/columns, and forbidden patterns; parametrized pytest suite; `make sql-eval` target for model-swap regression.
