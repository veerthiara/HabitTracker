# Phase 09 Rev 01 — SQL Analytics Core Implementation

## Overview

This revision establishes the **foundation** for a safe, reusable SQL analytics capability. It creates a **generic SQL analytics core** package (`habittracker/sql_analytics/`) plus a **HabitTracker-specific adapter** (`habittracker/domain/sql_catalog.py`).

**No SQL generation, validation, execution, or LangGraph integration is implemented in this revision.** Those are deferred to later revisions.

---

## Why the Original Implementation Was Refactored

The initial Phase 09 Rev 01 implementation (`habittracker/services/sql_schema_service.py` + `habittracker/schemas/sql_chat.py`) had several architectural problems:

| Problem | Impact |
|---------|--------|
| Generic + HabitTracker code mixed | Impossible to reuse in other projects |
| Hardcoded relationship strings in renderer | Renderer contained `habits.user_id -> users.id` — not generic |
| User scoping only in prompt text | No typed metadata for `is_user_scope` or scope strategy |
| Sensitive columns exposed | `embedding` column was rendered despite being internal |
| No provider abstraction | Catalog couldn't be swapped without modifying core |
| Tests only validated self | Tests compared hardcoded expectations to hardcoded implementation |

The refactor separates **generic reusable core** from **application-specific adapter**, enabling:
- Other projects to supply their own catalog via `SqlCatalogProvider` protocol
- Deterministic, domain-neutral prompt rendering
- Explicit metadata for user scoping, sensitive columns, and selectability
- Tests that verify against actual SQLAlchemy ORM metadata

---

## Package Structure

```
backend/habittracker/
├── sql_analytics/                    # Generic reusable core (zero HabitTracker deps)
│   ├── __init__.py                   # Public exports
│   ├── contracts.py                  # All Pydantic models
│   ├── catalog.py                    # SqlCatalogProvider protocol + implementations
│   ├── renderer.py                   # SqlSchemaContextRenderer (domain-neutral)
│   └── settings.py                   # SqlAnalyticsSettings (env-driven)
│
├── domain/                           # HabitTracker-specific adapter
│   ├── __init__.py
│   └── sql_catalog.py                # 6 tables, 6 relationships, business rules
│
├── tests/
│   ├── habittracker/sql_analytics/   # 61 generic tests (fake domain: customers/orders)
│   │   ├── test_contracts.py
│   │   ├── test_catalog.py
│   │   └── test_renderer.py
│   └── habittracker/domain/          # 21 adapter tests (verify against ORM)
│       └── test_sql_catalog.py
```

---

## Approved HabitTracker Tables (6)

| Table | User Scoped | Selectable | Purpose |
|-------|-------------|------------|---------|
| `users` | No | No | Root entity for FK references |
| `habits` | Yes (`user_id`) | Yes | Habit definitions |
| `habit_logs` | Yes (`user_id`) | Yes | Daily completions |
| `bottle_events` | Yes (`user_id`) | Yes | Hydration events |
| `daily_summaries` | Yes (`user_id`) | Yes | Pre-computed summaries |
| `notes` | Yes (`user_id`) | Yes* | Journal notes (*content gated) |

### Excluded Tables
None — all ORM tables are represented. `users` is included for relationship metadata but `allowed_for_select=False`.

### Excluded Columns
- `notes.embedding` — **excluded entirely** from approved catalog (sensitive, internal use only)

---

## User Scope Representation

| Mechanism | Description |
|-----------|-------------|
| `SqlTableDefinition.user_scoped: bool` | Table-level flag |
| `SqlTableDefinition.scope_strategy: "direct" \| "indirect" \| "public"` | How to apply user filtering |
| `SqlColumnDefinition.is_user_scope: bool` | Column that holds the user identifier |
| `SqlTableDefinition.scope_description: str \| None` | Documents join path for indirect scope |

The renderer emits `User scoped: yes/no` and marks user-scope columns with `user scope` tag.

---

## Notes Content Policy

| Setting | Effect |
|---------|--------|
| `SQL_QA_ALLOW_NOTE_CONTENT=false` (default) | `notes.content` **excluded** from catalog |
| `SQL_QA_ALLOW_NOTE_CONTENT=true` | `notes.content` included as selectable column |

**Rationale:** Semantic retrieval (pgvector) is the preferred path for note meaning. Full-text SQL queries on notes are discouraged.

**Embedding column** (`notes.embedding`) is **never exposed** — marked `sensitive=True`, excluded from catalog entirely.

---

## How Another Project Supplies Its Own Catalog

```python
from habittracker.sql_analytics.contracts import (
    SqlColumnDefinition,
    SqlTableDefinition,
    SqlRelationshipDefinition,
    SqlSchemaCatalog,
)
from habittracker.sql_analytics.catalog import StaticSqlCatalogProvider
from habittracker.sql_analytics.renderer import SqlSchemaContextRenderer

# 1. Define your catalog (6 tables example)
catalog = SqlSchemaCatalog(
    catalog_name="inventory",
    catalog_version="1",
    dialect="postgresql",
    tables=(
        SqlTableDefinition(
            name="products",
            description="Product catalog",
            user_scoped=False,
            columns=(
                SqlColumnDefinition(name="id", description="Product ID", data_type="uuid", is_primary_key=True),
                SqlColumnDefinition(name="name", description="Product name", data_type="varchar(255)", nullable=False),
                SqlColumnDefinition(name="price_cents", description="Price in cents", data_type="integer", nullable=False),
            ),
        ),
        SqlTableDefinition(
            name="orders",
            description="Customer orders",
            user_scoped=True,
            columns=(
                SqlColumnDefinition(name="id", description="Order ID", data_type="uuid", is_primary_key=True),
                SqlColumnDefinition(name="customer_id", description="Buyer", data_type="uuid", is_foreign_key=True, foreign_key_target="customers.id", is_user_scope=True),
                SqlColumnDefinition(name="total_cents", description="Order total", data_type="integer", nullable=False),
            ),
        ),
        # ... more tables
    ),
    relationships=(
        SqlRelationshipDefinition(
            left_table="orders",
            left_column="customer_id",
            right_table="customers",
            right_column="id",
            relationship_type="many_to_one",
            description="Orders belong to customers",
        ),
    ),
    global_rules=(
        "Only SELECT statements allowed",
        "Always filter by user_id on user-scoped tables",
    ),
)

# 2. Wrap in provider
provider = StaticSqlCatalogProvider(catalog)

# 3. Render for LLM prompt
renderer = SqlSchemaContextRenderer()
schema_context = renderer.render(provider.get_catalog())

# schema_context is now a deterministic, domain-neutral prompt string
```

---

## What Remains Unimplemented (Explicit Non-Goals)

| Feature | Deferred To |
|---------|-------------|
| Text-to-SQL prompting / provider calls | Rev 03+ |
| SQL parser / validator | Rev 04+ |
| SQL executor / read-only session | Rev 04+ |
| Row-level security enforcement | Rev 04+ |
| LangGraph SQL path / nodes | Rev 06+ |
| Answer generation from SQL results | Rev 05+ |
| SQL repair / reflection / retries | Rev 11+ |
| LangSmith / DeepEval / Promptfoo integration | Rev 10+ |
| Feedback UI (thumbs up/down) | Rev 12+ |

---

## Verification Commands

```bash
# From backend/
poetry run pytest tests/habittracker/sql_analytics -q    # 61 generic tests
poetry run pytest tests/habittracker/domain -q           # 21 adapter tests
poetry run pytest tests/habittracker/services -q         # existing service tests
poetry run pytest tests/habittracker/graph -q            # existing graph tests
poetry run pytest -q                                      # all 323 tests
```

All 323 tests pass.