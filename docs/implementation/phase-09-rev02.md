# Phase 09 Rev 02 — SQL Generation Service

## Summary

This revision implements a reusable, provider-agnostic SQL generation service that converts natural-language questions into structured SQL candidates. The implementation follows the existing architectural patterns and maintains strict separation between generic reusable code and HabitTracker-specific code.

## Changes

### Contracts (`habittracker/sql_analytics/contracts.py`)

- Renamed `SQLGenerationRequest` → `SqlGenerationRequest`
- Renamed `SQLExecutionResult` → `SqlExecutionResult`
- Consistent naming convention across all contracts:
  - `SqlGenerationRequest`
  - `GeneratedSql`
  - `SqlValidationResult`
  - `SqlExecutionResult`
  - `SqlAnswerResult`

### Generation Service (`habittracker/sql_analytics/generation.py`)

Rewritten with clean architecture:

**New exceptions:**
- `SqlGenerationError` - Base error for SQL generation failures
- `SqlGenerationResponseError` - Raised when provider response cannot be parsed

**Key improvements:**
- Uses `GeneratedSql.model_validate()` for strict pydantic validation
- Provider exceptions wrapped in `SqlGenerationResponseError`
- Invalid confidence values (outside 0-1) raise `SqlGenerationResponseError`
- Non-list collection fields (referenced_tables, referenced_columns) raise `SqlGenerationResponseError`
- Provider exceptions (`ChatCompletionError`) propagate directly
- Clean top-level imports, no `TYPE_CHECKING` gymnastics
- Uses `GeneratedSql.model_validate()` for strict pydantic validation
- Removed manual field extraction logic that silently discarded invalid data

**API:**
```python
class SqlGenerationService:
    def __init__(
        self,
        provider: ChatProvider,
        catalog_provider: SqlCatalogProvider,
        renderer: SqlSchemaContextRenderer | None = None,
    ) -> None: ...

    def generate(
        self,
        question: str,
        user_id: str | int,
        conversation_history: tuple[dict[str, str], ...] = (),
    ) -> GeneratedSql: ...

    def _parse_response(self, response_text: str) -> GeneratedSql: ...
```

### Prompts (`habittracker/sql_analytics/prompts.py`)

- Updated type hints to use `SqlGenerationRequest`
- System prompt enforces:
  - Single SELECT statement (WITH allowed)
  - `:user_id` bound parameter for user-scoped tables
  - No INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE
  - No multiple statements, no system schemas
  - LIMIT for row-list queries
  - JSON-only output with specified shape

### Tests

**New test file:** `tests/habittracker/sql_analytics/test_generation.py`

**Test coverage:**
- Service generation with valid/invalid inputs
- Provider message structure validation
- Conversation history handling
- Error propagation (empty question, provider errors)
- User ID binding (int converted to string, not embedded in SQL)
- Response parsing: valid JSON, whitespace, markdown fences, missing fields
- Strict validation: non-list collections, confidence bounds, empty SQL, invalid JSON
- Custom exceptions properly raised and caught
- Integration with real renderer and catalog provider

**Removed:**
- Duplicated `_fake_catalog` and `MockChatProvider` definitions
- Permissive parsing tests (confidence clamping, non-list coercion)

**Updated:**
- `test_generation.py` uses `SqlGenerationRequest` consistently
- Tests assert strict behavior (exceptions raised for invalid data)
- Custom exceptions properly tested
- Exception hierarchy verified

### Prompt Tests

Updated `test_prompts.py` to use `SqlGenerationRequest` and fixed system prompt assertions to match actual prompt text.

### Exports

Updated `habittracker/sql_analytics/__init__.py` to export:
- `SqlGenerationError`
- `SqlGenerationResponseError`

### Documentation

Created `docs/implementation/phase-09-rev02.md` documenting the implementation.

## Verification

All 369 tests pass:
```
369 passed in 0.71s
```

Including 112 sql_analytics tests (40 generation, 72 contracts/catalog/renderer) and 257 existing tests.