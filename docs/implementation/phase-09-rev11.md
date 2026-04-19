# Phase 09 Rev 11 — Evaluation Set and Regression Harness

## Goal

Make model changes measurable so future prompt edits or model swaps can be evaluated against a fixed baseline rather than ad hoc manual testing.

## Key Decisions

- **Split into two test classes, not one** — `TestIntentClassification` runs the keyword-based classifier (no LLM, sub-millisecond) and always passes regardless of model. `TestTemplateSqlAssertions` renders template SQL (no LLM, deterministic) and checks structural invariants. Separating them makes it obvious whether a failure is a routing regression or a SQL structure regression.

- **Fixture-driven parametrize over inline parametrize** — storing the eval set in `tests/fixtures/sql_eval_questions.json` means the baseline can be updated without touching test code. Adding a new question is one JSON entry; the test suite picks it up automatically.

- **Template path only, no LLM mocking** — all 23 fixture questions that use a known intent exercise the template renderer directly. UNKNOWN-intent questions (`which_habit_missed`, `weekday_pattern`, `habit_streak`) are included for intent-classification coverage only and skip the SQL assertion step. LLM output evaluation (recording model responses) is deferred to a future revision.

- **One fixture entry fixed during run** — "How many times did I complete a habit" correctly routes to `habit_completion_rate` (not `count_logs`) because `_HABIT_RATE_KEYWORDS` includes `"how many times did i complete"` and is checked before `_COUNT_KEYWORDS`. The fixture was updated to use "How many habit log entries did I make" for the count_logs case.

- **Universal invariants checked on every template result** — `:user_id` bind param, `LIMIT`, and `SELECT` are asserted on every rendered SQL to guard against template regressions that would bypass the validator.

## Architectural Context

The eval harness sits entirely outside the application code. It depends only on `SqlIntentClassifier` and `SqlTemplateRenderer` — the two stateless, deterministic components of the SQL path. No DB session, no LLM call, no Postgres connection required.

```
tests/fixtures/sql_eval_questions.json
         │
         │  (parametrize)
         ▼
TestIntentClassification
  └─ SqlIntentClassifier.classify(question)
       └─ assert == expected_intent

TestTemplateSqlAssertions
  └─ SqlTemplateRenderer.render(params)
       └─ assert table, columns, invariants, not forbidden patterns
```

**Model-swap workflow**: change `OLLAMA_CHAT_MODEL` (one env var or one line in `core/config.py`), then run `make sql-eval`. The intent and template tests are model-independent and will continue passing. When LLM-backed eval cases are added in a future revision, failures there directly show the quality delta across model versions.

## Scope Implemented

- 23 fixture entries covering all 7 known intents (3 TOTAL_METRIC, 3 AVERAGE_PER_DAY, 3 COUNT_LOGS, 3 DAILY_TREND, 3 TOP_DAY, 2 HABIT_COMPLETION_RATE, 3 COMPARE_PERIODS) and 3 UNKNOWN questions
- Each fixture entry: `id`, `question`, `expected_intent`, `template_params`, `expected_tables`, `expected_columns`, `must_not_contain`
- `TestIntentClassification`: 23 parametrized intent routing tests
- `TestTemplateSqlAssertions`: 20 parametrized SQL structure tests (3 UNKNOWN skipped)
- `make sql-eval` target runs only the eval suite
- 43 new tests; total test count: 582 (all passing)

## Files Changed

```
backend/tests/fixtures/sql_eval_questions.json                             (new)
backend/tests/habittracker/services/sql/test_sql_eval.py                   (new)
Makefile                                                                   (sql-eval target)
```

## Notes

- The fixture is intentionally broad: questions vary by phrasing, domain (water vs habits), and time window to catch classifier edge cases.
- `must_not_contain` patterns (`" AS T1"`, `" AS T2"`, `" AS be"`, `"JOIN users"`, `"%(user_id)s"`) are included in every template entry to guard against template changes that accidentally re-introduce alias patterns.
- Template SQL assertions are structure-only — they do not assert specific SQL text. This keeps the fixture stable if template formatting changes while semantics stay correct.

## Next Step

Phase 09 is complete. The SQL analytics path is fully operational: schema-grounded generation → alias-free template SQL → strict validation → one-pass repair → natural-language answer, with a regression harness to measure future model changes.

Next phase to begin: Phase 10 (LangGraph multi-step orchestration) or Phase 07 UI polish, per the roadmap.
