# Phase 09 — Safe SQL Question Answering

## Status

Planned

## Goal

Allow the AI assistant to answer flexible analytical questions by:

1. understanding the approved application database schema,
2. generating read-only PostgreSQL queries,
3. validating generated SQL before execution,
4. executing the query safely,
5. converting the returned rows into a grounded natural-language answer,
6. integrating the SQL capability into the existing LangGraph workflow.

The SQL capability must remain separate from:

- handwritten repository queries,
- semantic note retrieval,
- API transport logic,
- model-provider implementations.

---

# Why This Phase Exists

The application currently has two primary ways of answering questions.

## Existing structured repository path

This path handles known questions through handwritten repository methods.

Examples:

- How many bottle events happened today?
- What habits did I complete?
- What is my current dashboard summary?
- What is my habit streak?

This path is:

- predictable,
- fast,
- testable,
- grounded in explicit business logic.

However, it only supports questions that have already been implemented.

## Existing semantic retrieval path

This path searches embedded notes using pgvector.

Examples:

- What patterns appear in my notes?
- Did I mention being tired on low-hydration days?
- What did I write about struggling with exercise?

This path is useful for:

- unstructured text,
- semantic similarity,
- note-based reasoning.

However, semantic retrieval is not ideal for exact database aggregation.

## Missing SQL analytics path

The application cannot yet answer flexible analytical questions such as:

- Which weekday has the highest average number of bottle events?
- Compare my habit completion rate this month with last month.
- Which habit was missed most often during the last 90 days?
- How many days had both low hydration and incomplete habits?
- Show my best five days by total habit completion.
- What percentage of days did I complete every active habit?
- Did hydration improve after I created a particular habit?

These questions require dynamic filtering, grouping, aggregation, joins, and date comparison.

Phase 09 introduces a third answer path:

```text
Natural-language question
        ↓
Schema context
        ↓
SQL generation
        ↓
SQL validation
        ↓
Read-only execution
        ↓
Result normalization
        ↓
Grounded answer



Future Extensions

Phase 09 prepares the application for:

Phase 10 — Evaluation and Provider-Neutral Observability
deterministic evaluation dataset,
DeepEval or equivalent harness,
Langfuse/LangSmith switch,
provider comparisons,
regression testing.
Phase 11 — Reflection and Runtime Quality Control
SQL repair attempt,
evidence sufficiency checks,
answer grounding review,
conditional retries,
safe regeneration.
Phase 12 — User Feedback
thumbs up/down,
feedback reasons,
trace-linked feedback,
conversion of failures into evaluation cases.