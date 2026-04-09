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