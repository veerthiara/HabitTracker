# Phase 09 Rev 06 — Wire Answer Service + /api/v1/sql/ask endpoint

## Goal

Complete the SQL analytics lane end-to-end: wire `SqlAnswerService` into
`SqlPipelineService`, extend `SqlPipelineResult` with an `answer` field, and
expose `POST /api/v1/sql/ask` so the pipeline can be exercised through HTTP.

## Key Decisions

- **Stage 4 inside `SqlPipelineService`**: The answer service is the natural
  fourth stage of the existing generation→validation→execution chain. Adding it
  here keeps the pipeline self-contained and means the LangGraph node in the
  next phase just calls `sql_pipeline_service.run()` and receives a complete
  result, including the answer text.

- **Never-raise contract preserved**: `SqlAnswerError` is caught and encoded as
  `success=False, failure_reason="Answer generation failed: ..."`. The
  execution result is still returned so callers can inspect the rows even when
  the LLM answer fails.

- **`SqlAskRequest` / `SqlAskResponse` as public API schemas**: The pipeline
  schemas (`SqlGenerationRequest`, `SqlPipelineResult`) are internal contracts.
  The HTTP layer gets its own thin schemas in `schemas/sql_chat.py` to keep the
  public surface stable and independently versioned.

- **Empty-string guard on `generated_sql`**: `SqlPipelineResult.generated_sql`
  is an empty string when generation fails. The endpoint normalises this to
  `None` in the response so the API consumer never receives an empty string
  where `null` is more semantically correct.

## Architectural Context

The SQL analytics lane is now fully integrated:

```
POST /api/v1/sql/ask
      │
      ▼
SqlPipelineService.run()
  ├─ Stage 1: SqlGenerationService  → SQL text
  ├─ Stage 2: SqlValidationService  → safety check
  ├─ Stage 3: SqlExecutionService   → rows
  └─ Stage 4: SqlAnswerService      → answer text   ← wired here
      │
      ▼
SqlAskResponse { answer, success, failure_reason, generated_sql }
```

The LangGraph `sql_analytics_node` (Phase 10) will call
`sql_pipeline_service.run()` directly and read `result.answer` — no changes
needed to this layer for that integration.

## Scope Implemented

- `schemas/sql_chat.py` — `SqlPipelineResult.answer` field; `SqlAskRequest` and `SqlAskResponse` public schemas
- `services/sql/pipeline_service.py` — Stage 4 (answer), `answer_svc` constructor param, updated singleton
- `api/v1/sql.py` — `POST /api/v1/sql/ask` endpoint (new file)
- `server.py` — register `sql.router`
- `tests/habittracker/services/sql/test_sql_pipeline_service.py` — 9 new `TestAnswerStage` tests; `_make_pipeline` updated; two direct constructor calls updated

## Files Changed

```
backend/habittracker/schemas/sql_chat.py
backend/habittracker/services/sql/pipeline_service.py
backend/habittracker/api/v1/sql.py                       (new)
backend/habittracker/server.py
backend/tests/habittracker/services/sql/test_sql_pipeline_service.py
docs/implementation/phase-09-rev06.md                    (this file)
```

## Notes

- 405 tests total (396 from rev-05 + 9 new pipeline answer-stage tests).
- No API-layer tests added — the endpoint is a thin call-through; service-layer
  test coverage is the appropriate level.
- `POST /api/v1/sql/ask` is a dev/debug endpoint for now. It will be replaced
  by the LangGraph chat routing in Phase 10 once `sql_analytics_node` is wired.

## Next Step

Phase 10 — LangGraph SQL routing node: add a `sql_analytics` intent path to
the existing chat graph, routing questions with SQL-answerable intent to
`sql_pipeline_service.run()` and returning `ChatResponse` with evidence items
built from `SqlExecutionResult`.
