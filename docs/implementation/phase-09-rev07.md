# Phase 09 Rev 07 — Intent Ordering Fix + Logging + SQL Integration Tests

## Goal

Fix a routing bug where analytical questions containing domain keywords (e.g. "average water per day over the last 30 days") incorrectly routed to `bottle_activity` instead of `sql_analytics`. Also commit logging improvements and SQL path integration tests that were written during Rev 06 but left uncommitted.

## Key Decisions

- **SQL_ANALYTICS checked before BOTTLE/HABIT in `classify_intent()`** — SQL keywords (aggregation, time ranges, comparison operators) are specific enough that they unambiguously signal analytics intent regardless of which domain entities appear in the message. Simple lookup questions ("how much water today?") contain none of the SQL keywords and still fall through to the correct path.
- **Keyword order in the source file mirrors evaluation order** — the `_SQL_ANALYTICS_KEYWORDS` constant is now declared above `_BOTTLE_KEYWORDS` and `_HABIT_KEYWORDS`. This makes the priority relationship visible at the point of definition, not just in `classify_intent()`.
- **No changes to the SQL keyword set itself** — the keyword set was already safe from false-positive matches. The bug was purely an ordering issue.

## Architectural Context

`classify_intent()` is the sole routing gate inside `classify_intent_node`. The LangGraph intent router sends all `SQL_ANALYTICS` messages to `sql_analytics_node → END`, bypassing `gather_context_node` and `generate_answer_node`. This keeps analytical queries fast and avoids embedding lookups for structured data questions.

```
user message
     │
classify_intent_node
     │
     ├─ SQL_ANALYTICS ──► sql_analytics_node ──► END
     ├─ BOTTLE_ACTIVITY ─┐
     ├─ HABIT_SUMMARY  ──┤
     ├─ NOTE_PATTERN   ──┤
     └─ GENERAL        ──► gather_context_node ──► generate_answer_node ──► END
```

**Before this fix:**
- "Tell me in last 30 days average water drank per day"
  - matches `_BOTTLE_KEYWORDS` ("water") → `BOTTLE_ACTIVITY` ✗

**After this fix:**
- Same message
  - SQL check runs first, matches "last 30" + "average" + "per day" → `SQL_ANALYTICS` ✓

## Scope Implemented

### Bug fix
- `chat_intent_service.py` — move SQL_ANALYTICS check before BOTTLE/HABIT; reorder constant declarations; update docstring evaluation-order comment.

### Logging (uncommitted from Rev 06)
- `api/v1/chat.py` — `INFO` log at request entry (thread, message) and response exit (thread, intent, used_notes, answer length).
- `graph/nodes.py` — `classify_intent_node` and `gather_context_node` promoted from `DEBUG` to `INFO` so they appear in the default log level without extra configuration.

### Tests
- `test_chat_intent_service.py` — `TestClassifyIntentOrdering` updated with two new ordering cases:
  - `test_sql_beats_bottle_when_analytical`
  - `test_sql_beats_habit_when_analytical`
- `test_graph_integration.py` — `TestGraphSqlAnalyticsPath` class (from Rev 06, now committed); routing matrix extended with `"Tell me in last 30 days average water drank per day" → sql_analytics` case.

## Files Changed

```
backend/habittracker/services/chat_intent_service.py
backend/habittracker/api/v1/chat.py
backend/habittracker/graph/nodes.py
backend/tests/habittracker/services/test_chat_intent_service.py
backend/tests/habittracker/graph/test_graph_integration.py
docs/implementation/phase-09-rev07.md
```

## Notes

- All 441 tests pass after the change.
- Existing ordering tests remain valid: their messages ("Why is my water intake low?", "Did I drink water after my morning habit?") contain no SQL keywords, so they still route to BOTTLE/HABIT as before.
- `" rank"` (leading space) is intentional to avoid matching "drank" via substring.

## Next Step

Phase 10 — or further SQL analytics hardening (prompt improvements, schema context injection, result formatting).
