# Phase 09 Rev 08-09 — Template-Backed SQL Generation and Schema-Grounded Validation

## Goal

Rev 08: Reduce free-form SQL generation for common analytics questions by routing them through fixed, pre-validated SQL templates. Only truly novel questions fall through to the LLM generator.

Rev 09: Prevent schema hallucinations from reaching Postgres by checking generated SQL against known-good column metadata before execution.

Both revisions were implemented together and committed as a single unit.

## Key Decisions

- **Keyword-based intent classifier, no LLM call** — `SqlIntentClassifier` maps questions to 7 `SqlAnalyticsIntent` values using keyword sets. Same approach as the existing `chat_intent_service`: fast, deterministic, and easy to unit-test without mocking an LLM.

- **Narrow LLM call for parameter extraction, not full SQL** — `SqlParameterExtractor` asks the LLM only for a small JSON payload (`table`, `metric_col`, `ts_col`, `interval_days`). This is far more reliable than asking the same model to produce a complete, syntactically correct SQL string.

- **Fixed templates with safe defaults** — `SqlTemplateRenderer` holds 7 static SQL templates that are alias-free, always include `<table>.user_id = :user_id`, and always include `LIMIT`. Validated once at write time; cannot drift across model updates.

- **Three new validation checks in Rev 09** — alias blocking (`_check_no_table_aliases`), column existence (`_check_known_columns`), and user_id filter presence (`_check_user_id_filter`) added to `SqlValidationService`. These catch the most common LLM mistakes before the query reaches Postgres.

- **`column_set` added to `SchemaContext`** — a `frozenset` of `(table_name, col_name)` tuples enables O(1) column lookups in the validator without iterating the full schema on every check.

- **`generation_method` field on results** — `SqlGenerationResult` and `SqlPipelineResult` gain a `GenerationMethod` enum field (`TEMPLATE` / `LLM`) for observability and future evaluation tooling.

## Architectural Context

The pipeline still has the same 4 stages (generate → validate → execute → answer). Rev 08 inserts an intent-classify + parameter-extract step before the generation stage. Rev 09 extends the validate stage with schema-grounding checks.

```
user question
     │
SqlIntentClassifier (keyword match)
     │
     ├─ known intent ──► SqlParameterExtractor (LLM: JSON only)
     │                        │
     │                   SqlTemplateRenderer (fixed SQL)
     │                        │
     └─ UNKNOWN ──────────────┤
                              │
                         SqlValidationService
                          • SELECT only
                          • allowed tables
                          • no aliases            ← Rev 09
                          • known columns         ← Rev 09
                          • user_id filter        ← Rev 09
                              │
                         SqlExecutionService
                              │
                         SqlAnswerService
```

## Scope Implemented

- `SqlAnalyticsIntent` enum: `TOTAL_METRIC`, `AVERAGE_PER_DAY`, `COUNT_LOGS`, `DAILY_TREND`, `TOP_DAY`, `HABIT_COMPLETION_RATE`, `COMPARE_PERIODS`, `UNKNOWN`
- `SqlIntentClassifier`: keyword sets per intent; evaluation order prevents false-positive overlaps
- `SqlParameterExtractor`: narrow LLM extraction with per-intent safe defaults so partial responses still produce valid queries
- `SqlTemplateRenderer`: 7 `@staticmethod` methods; raises `SqlTemplateError` for `UNKNOWN` intent
- `SqlValidationService`: three new check methods, all wired into `validate()`
- `SchemaContext.column_set`: computed `frozenset` property
- `SqlPipelineService`: wires template path before LLM fallback; records `generation_method` on result

## Files Changed

```
backend/habittracker/schemas/sql_template.py              (new)
backend/habittracker/schemas/sql_chat.py                  (GenerationMethod, generation_method field)
backend/habittracker/schemas/sql_schema.py                (column_set property)
backend/habittracker/services/sql/intent_classifier.py    (new)
backend/habittracker/services/sql/parameter_extractor.py  (new)
backend/habittracker/services/sql/template_renderer.py    (new)
backend/habittracker/services/sql/errors.py               (SqlTemplateError, SqlParameterExtractionError)
backend/habittracker/services/sql/validation_service.py   (_check_no_table_aliases, _check_known_columns, _check_user_id_filter)
backend/habittracker/services/sql/pipeline_service.py     (wire template path; generation_method on result)
backend/tests/habittracker/services/sql/test_sql_intent_classifier.py   (new)
backend/tests/habittracker/services/sql/test_sql_template_renderer.py   (new)
backend/tests/habittracker/services/sql/test_sql_parameter_extractor.py (new)
backend/tests/habittracker/services/sql/test_sql_validation_service.py  (alias, column, user_id checks)
backend/tests/habittracker/services/sql/test_sql_pipeline_service.py    (template path tests)
docs/roadmap/phase-09-sql-question-answering-detailed.md  (Rev 08-11 plan added)
```

## Notes

- Free-form LLM generation remains as a clearly-labelled fallback (`generation_method=LLM`). It is not removed; it handles novel questions outside the 7 known intents.
- The `_USER_ID_FILTER` regex in the validator accepts both `table.user_id = :user_id` and bare `user_id = :user_id` to avoid breaking existing LLM-generated SQL tests.
- `_TABLE_ALIAS` regex exempts aggregate aliases (`COUNT(*) AS n`) while blocking FROM-clause aliases (`FROM t AS x`).
- 521 tests passing after these revisions.

## Next Step

Rev 10 — One-pass SQL repair loop: catch execution failures, send failed SQL + DB error to LLM for a single repair attempt, re-validate before retry.
