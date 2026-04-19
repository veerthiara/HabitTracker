# Phase 09 — SQL Question Answering

## Goal
Allow the assistant to answer flexible analytical questions by generating safe read-only SQL against the app database.

## Why
The current repository-based flow handles known question types well, but it does not support broad ad hoc analytical questions.

This phase adds a separate SQL analytics path so the assistant can answer questions such as:
- Which day had the most bottle pickups in the last 30 days?
- What is my average habit completion count by weekday?
- Which habit do I miss most often?
- Compare hydration this week vs last week
- Show trends that are not already hardcoded in repository functions

## Scope
- schema-aware SQL generation
- read-only SQL execution
- validation and safety guardrails
- integration into LangGraph routing
- answer generation from SQL results
- optional debug metadata for generated SQL during development

## Out of scope
- write queries
- arbitrary unrestricted SQL
- automatic schema modification
- replacing the existing repository-based flow
- reflection/repair loops beyond basic validation
- feedback collection and tuning loops

---

## Design Principles

### 1. Keep SQL as a separate capability
Generated SQL should be implemented as a separate analytics path, not mixed into the existing repository layer.

### 2. Preserve the repository path
Existing repositories remain the preferred path for:
- exact counts
- stable dashboard metrics
- known question types
- trusted business logic

### 3. Use SQL for flexible analytical questions
The SQL path should handle:
- grouping
- filtering
- comparison
- aggregation
- exploratory analytical questions not already supported by repositories

### 4. Keep it read-only and safe
Only safe `SELECT` queries are allowed.
No `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, or unrestricted query execution.

### 5. Route through LangGraph
LangGraph should decide whether a question goes to:
- repository path
- semantic retrieval path
- SQL path

---

## Suggested Architecture

### New service area
Recommended additions:

- `habittracker/services/sql_schema_service.py`
- `habittracker/services/sql_generation_service.py`
- `habittracker/services/sql_validation_service.py`
- `habittracker/services/sql_execution_service.py`
- `habittracker/services/sql_answer_service.py`

### Optional schema/response file
- `habittracker/schemas/sql_chat.py`

### Graph integration
Reuse the existing graph layer:
- `habittracker/graph/routing.py`
- `habittracker/graph/nodes.py`
- `habittracker/graph/state.py`

The SQL lane should become a new graph path rather than being embedded inside existing chat services.

---

## Revision Plan

### Rev 01 — SQL schema exposure and contracts

#### Goal
Define the safe schema context and response contracts needed for text-to-SQL.

#### Scope
- create a schema summary for the LLM describing only approved tables and columns
- include business-friendly descriptions where useful
- define request/response models for internal SQL generation and execution
- identify which tables are allowed in SQL mode

#### Recommended allowed tables (initial)
- users
- habits
- habit_logs
- bottle_events
- daily_summaries
- notes (optional, only if clearly useful)

#### Deliverable
- a clear schema context that can be injected into prompts
- internal contracts for SQL generation and execution

#### Notes
Do not expose every possible ORM detail.
The schema summary should be compact, intentional, and stable.

---

### Rev 02 — Safe read-only SQL execution layer

#### Goal
Build a controlled execution layer for generated SQL.

#### Scope
- add a SQL execution service that accepts SQL text
- enforce read-only behavior
- reject forbidden commands such as:
  - insert
  - update
  - delete
  - drop
  - alter
  - truncate
- add row limit protection
- add timeout protection
- return structured rows and column metadata

#### Deliverable
- backend service capable of safely executing approved analytical SQL

#### Notes
This service should not live inside repository modules.
It is a separate SQL analytics capability.

---

### Rev 03 — SQL generation from natural language

#### Goal
Translate natural-language analytical questions into safe SQL.

#### Scope
- add a SQL generation service
- use the approved schema summary as prompt context
- generate SQL only for supported analytical questions
- keep the prompt focused on:
  - `SELECT`
  - aggregates
  - grouping
  - filtering
  - ordering
  - row limits

#### Deliverable
- natural-language question → generated SQL text

#### Notes
The output at this stage is SQL only, not the final user answer.

#### Example questions
- Which weekday has the highest average number of bottle events?
- What is my average number of completed habits per day this month?
- Which habit do I miss most often?

---

### Rev 04 — SQL validation and execution pipeline

#### Goal
Validate generated SQL and run it safely.

#### Scope
- validate generated SQL before execution
- enforce:
  - read-only
  - allowed tables only
  - row limits
  - no multiple statements
- execute validated SQL
- return structured query results
- expose development/debug metadata internally:
  - generated SQL
  - validation result
  - execution status

#### Deliverable
- end-to-end text-to-SQL backend pipeline:
  - question
  - SQL generation
  - validation
  - execution
  - result set

#### Notes
At this stage, failure should return a safe fallback instead of crashing the chat flow.

---

### Rev 05 — SQL result-to-answer generation

#### Goal
Turn SQL results into a grounded natural-language answer.

#### Scope
- add a service that converts SQL results into:
  - answer text
  - optional evidence items
  - optional SQL debug info in dev mode
- ensure the LLM answers only from the SQL result set
- add fallback if result set is empty or insufficient

#### Deliverable
- SQL results can be transformed into user-facing answers

#### Notes
The answer should be grounded in actual rows returned, not in the model’s guess.

---

### Rev 06 — LangGraph routing integration

#### Goal
Add the SQL path into the existing chat graph.

#### Scope
- update routing rules so some questions are sent to the SQL lane
- keep repository path for known exact questions
- keep semantic retrieval path for note-based/pattern questions
- add graph node(s) for:
  - SQL generation
  - validation/execution
  - SQL answer generation

#### Deliverable
- LangGraph can choose among:
  - repository-based answering
  - semantic retrieval
  - SQL-based answering

#### Notes
Do not remove the existing repository path.
SQL is an additional capability, not a replacement.

---

### Rev 07 — Guardrails, tests, and developer visibility

#### Goal
Make the SQL path safe and testable.

#### Scope
- add tests for:
  - safe SQL validation
  - forbidden statement rejection
  - row limits
  - result formatting
  - graph routing into SQL path
- add structured logging or Langfuse metadata for:
  - generated SQL
  - validation outcome
  - execution duration
- optionally expose SQL in dev/debug mode only

#### Deliverable
- SQL path is safe, observable, and testable

---

### Rev 08 — Structured intent extraction and template-backed SQL

#### Goal
Reduce free-form SQL generation for common analytics questions by routing them
through fixed, pre-validated SQL templates. Only truly novel questions fall
through to the LLM generator.

#### Motivation
Small local LLMs reliably misuse table aliases, omit the column name in the
`user_id` filter, or join unnecessary tables. The root cause is that free-form
generation requires the model to get *every* syntactic detail right. Fixed
templates remove all of that risk for the question families users ask most often.

#### Scope
- Define a `SqlAnalyticsIntent` enum covering common question families:
  - `TOTAL_METRIC` — total amount over a time window (e.g. total ml this week)
  - `AVERAGE_PER_DAY` — average per calendar day over a window
  - `COUNT_LOGS` — number of rows/events over a window
  - `DAILY_TREND` — per-day breakdown over a window
  - `TOP_DAY` — which single day had the most/least of a metric
  - `HABIT_COMPLETION_RATE` — % of days a habit was completed
  - `COMPARE_PERIODS` — this week vs last week, this month vs last month
  - `UNKNOWN` — does not match any template; falls back to LLM generation
- Add a `SqlIntentClassifier` that maps a natural-language question to one of the
  above intents by keyword matching (same approach as `chat_intent_service` —
  fast, no LLM call).
- Add a `SqlParameterExtractor` that uses the LLM to extract a small structured
  payload from the question:
  - `table` — which table to query (`bottle_events`, `habit_logs`, …)
  - `metric` — which column to aggregate (`volume_ml`, `id`, …)
  - `interval` — time window in days (7, 30, 90, or null)
  - `grouping` — optional group-by column (`DATE(event_ts)`, `logged_date`, …)
  This is a narrowly-scoped extraction task (JSON output only), far less error-prone
  than generating full SQL.
- Add a `SqlTemplateRenderer` that takes an intent + parameters and returns a
  fully-formed, alias-free, parameterised SQL string. All templates:
  - use full table names (no `AS` aliases)
  - include `<table>.user_id = :user_id`
  - include `LIMIT`
- Wire the new path in `SqlPipelineService`:
  1. classify intent
  2. if known → extract parameters → render template → validate → execute
  3. if `UNKNOWN` → existing LLM generation → validate → execute

#### Deliverable
- Common analytics questions produce template-rendered SQL, not LLM-generated SQL
- Free-form generation is a clearly-labelled fallback, not the primary path

#### Files (new)
- `services/sql/intent_classifier.py`
- `services/sql/parameter_extractor.py`
- `services/sql/template_renderer.py`
- `schemas/sql_template.py`
- `tests/habittracker/services/sql/test_sql_intent_classifier.py`
- `tests/habittracker/services/sql/test_sql_template_renderer.py`
- `tests/habittracker/services/sql/test_sql_parameter_extractor.py`

#### Files (modified)
- `services/sql/pipeline_service.py` — wire new path before fallback
- `schemas/sql_chat.py` — add `generation_method` field (template | llm) to result

---

### Rev 09 — SQL schema grounding and stricter validation

#### Goal
Prevent schema hallucinations from reaching Postgres by checking generated SQL
against known-good column metadata before execution.

#### Scope
- Extend `SqlValidationService` with two new checks:
  - `_check_no_aliases` — reject any SQL that contains ` AS ` (alias declaration)
    except inside aggregate expressions (`COUNT(*) AS n` is allowed; `FROM t AS x`
    is not)
  - `_check_known_columns` — for every `<table>.<column>` reference in the SQL,
    verify both the table and column exist in `SchemaContext`. Reject with a
    descriptive message listing the unknown references.
- Add `_check_user_id_filter` — reject SQL that does not contain
  `<approved_table>.user_id = :user_id` for at least one of the tables in the
  FROM clause.
- Make `SchemaContext` expose a `column_set` computed property:
  `{(table_name, col_name), …}` for O(1) lookups in the validator.
- Update the pipeline so validation failures trigger the repair loop (Rev 10)
  rather than returning a hard error to the user.

#### Deliverable
- Schema hallucinations (wrong column names, wrong table references, missing
  user_id filter) are caught before execution and never reach Postgres

#### Files (modified)
- `schemas/sql_schema.py` — `column_set` property on `SchemaContext`
- `services/sql/validation_service.py` — three new check methods; all wired into `validate()`
- `tests/habittracker/services/sql/test_sql_validation_service.py` — new cases for each check

---

### Rev 10 — One-pass repair loop for execution failures

#### Goal
Recover safely from predictable SQL mistakes without crashing the chat flow.

#### Scope
- Add a `SqlRepairService` that accepts:
  - original question
  - failed SQL
  - DB error message
  - schema summary
  Returns repaired SQL text (LLM call) or raises `SqlRepairError` if the model
  cannot fix it.
- Repair prompt includes:
  - the schema
  - the failed SQL
  - the exact DB error string
  - an explicit instruction to produce only the corrected SELECT
- Repair result is passed through the full validation pipeline before execution.
- Retry is attempted **once only**. A second failure returns a user-facing
  fallback ("I wasn't able to answer that question reliably — please try
  rephrasing.").
- `SqlPipelineResult` gains two new fields: `repair_attempted: bool` and
  `repair_error: str | None`.
- Both attempts (original SQL + repaired SQL) are logged at `WARNING` level with
  the DB error so they are visible in Langfuse.

#### Deliverable
- Transient LLM mistakes that produce invalid SQL are retried once automatically
- Users never see a raw Postgres error
- Both attempts are observable in logs

#### Files (new)
- `services/sql/repair_service.py`
- `services/sql/errors.py` — add `SqlRepairError`
- `tests/habittracker/services/sql/test_sql_repair_service.py`

#### Files (modified)
- `services/sql/pipeline_service.py` — catch execution errors, invoke repair, retry
- `schemas/sql_chat.py` — `repair_attempted`, `repair_error` fields

---

### Rev 11 — Evaluation set and regression harness

#### Goal
Make model changes measurable so future prompt edits or model swaps can be
evaluated against a fixed baseline rather than ad hoc manual testing.

#### Scope
- Create a fixture file `tests/fixtures/sql_eval_questions.json` containing at
  least 20 natural-language questions with:
  - `question` — the user's input
  - `expected_intent` — `SqlAnalyticsIntent` enum value
  - `expected_tables` — list of tables the SQL must reference
  - `expected_columns` — list of columns the SQL must reference
  - `must_not_contain` — patterns that must not appear (e.g. `" AS T"`, `"users"`)
- Add a pytest module `tests/habittracker/services/sql/test_sql_eval.py` that:
  - parametrizes over the fixture file
  - runs the full pipeline (generation → validation only, no DB) against a mock
    provider that returns pre-recorded LLM outputs
  - asserts intent classification, table/column presence, and forbidden patterns
- Add a `make sql-eval` Makefile target that runs only the eval suite.
- Designed so that swapping the Ollama model (Llama 3.2 → Qwen 2.5 Coder) is one
  config line change and re-running `make sql-eval` shows a pass/fail delta.

#### Deliverable
- Regression harness that catches prompt regressions before they reach
  production
- Baseline pass rate recorded for current model so future changes have a
  reference point

#### Files (new)
- `tests/fixtures/sql_eval_questions.json`
- `tests/habittracker/services/sql/test_sql_eval.py`
- `Makefile` — `sql-eval` target

---

## Suggested Routing Policy

### Use repository path for:
- exact bottle counts
- streak questions
- known dashboard summaries
- already-supported business logic

### Use semantic retrieval path for:
- note-based pattern questions
- explanation from notes
- contextual reflection from free text

### Use SQL path for:
- ad hoc analytical questions
- grouping and aggregation questions
- comparative questions not already handled by repositories
- flexible trend queries

---

## Suggested Response Shape

The public response can still reuse the main chat response contract.

Example:

```json
{
  "answer": "Your highest bottle pickup day in the last 30 days was March 12 with 14 bottle events.",
  "intent": "sql_analytics",
  "used_notes": false,
  "evidence": [
    {
      "type": "sql_result",
      "label": "Top day",
      "value": "2026-03-12: 14 bottle events"
    }
  ],
  "thread_id": "thread-123"
}