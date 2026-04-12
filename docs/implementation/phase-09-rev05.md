# Phase 09 Rev 05 — SQL Answer Service

## Goal

Convert a `SqlExecutionResult` (columns + rows from a live SQL query) into a
natural-language answer using a local LLM, completing the SQL analytics lane.

## Key Decisions

- **Empty result short-circuit**: When `row_count == 0` the service returns a
  hard-coded fallback string without calling the LLM. There is no data to ground
  the answer on, so an LLM call would either hallucinate or return a useless
  "I don't know". Skipping the call is faster and safer.

- **Prompt grounds the LLM strictly on the rows**: The system prompt passes the
  formatted table data and instructs the model to use *only* that data. The
  prompt also explicitly forbids mentioning SQL, table names, or column names so
  the answer reads as a plain data insight, not a technical log.

- **`_format_rows` as `@staticmethod`**: Row formatting has no dependency on
  instance state and must be unit-testable in isolation. A static method on the
  class satisfies both constraints without leaking a module-level helper.

- **`SqlAnswerError` wraps `ChatCompletionError`**: Callers (pipeline, future
  LangGraph node) only need to catch `SqlError` or `SqlAnswerError`. They should
  not need to import provider-layer errors.

- **No `EvidenceItem` at this layer**: The answer service returns raw text.
  Building `EvidenceItem` objects for the HTTP response is a concern of the chat
  context layer above, which has the full pipeline result to draw from.

## Architectural Context

The SQL analytics lane is now complete:

```
User question
      │
      ▼
SqlGenerationService   → LLM → SQL text
      │
      ▼
SqlValidationService   → static safety checks
      │
      ▼
SqlExecutionService    → Postgres → rows
      │
      ▼
SqlAnswerService       → LLM + rows → answer text   ← this revision
      │
      ▼
SqlPipelineService     (orchestration — updated in rev-06 to call answer)
      │
      ▼
LangGraph sql_analytics_node  (Phase 10)
```

`SqlPipelineService` is the integration point that will call `answer_service` in
the next revision; it is not modified here to keep this revision minimal.

## Flow

```
answer(question, execution_result)
  ├─ row_count == 0 → return EMPTY_RESULT_FALLBACK
  ├─ _format_rows(result)  → "habit | count\n---\nRunning | 3"
  ├─ _build_system_prompt(question, rows_text)
  ├─ provider.complete([system, user])
  │    └─ ChatCompletionError → raise SqlAnswerError
  └─ return answer_text.strip()
```

## Scope Implemented

- `services/sql/answer_service.py` — `SqlAnswerService` class + `sql_answer_service` singleton
- `services/sql/errors.py` — added `SqlAnswerError`
- `tests/habittracker/services/sql/test_sql_answer_service.py` — 26 unit tests

## Files Changed

```
backend/habittracker/services/sql/answer_service.py   (new)
backend/habittracker/services/sql/errors.py           (SqlAnswerError added)
backend/tests/habittracker/services/sql/test_sql_answer_service.py  (new)
docs/implementation/phase-09-rev05.md                 (this file)
```

## Notes

- 396 tests total (370 from rev-04 + 26 new).
- The answer service is not yet wired into `SqlPipelineService`; that join
  happens in rev-06 alongside `SqlPipelineResult` schema extension.
- Row formatting is intentionally compact (pipe-separated) to reduce token
  usage. If max rows is 200 (`SQL_MAX_ROWS`) this stays well under typical
  context windows.

## Next Step

Rev 06 — wire `SqlAnswerService` into `SqlPipelineService.run()`, extend
`SqlPipelineResult` with `answer: str | None`, and expose a
`POST /api/v1/sql/ask` endpoint for end-to-end testing.
