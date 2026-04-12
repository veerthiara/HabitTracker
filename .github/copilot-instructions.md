# Copilot Instructions

## Project workflow
This repository is built phase by phase and revision by revision.

Branch naming convention:
- `phase-01-bootstrap-rev-01`
- `phase-02-core-db-table-implementation-rev-01`
- `phase-02-core-db-table-implementation-rev-02`

Documentation naming convention:
- `docs/implementation/phase-01-rev01.md`
- `docs/implementation/phase-02-rev01.md`
- `docs/implementation/phase-02-rev02.md`

Ensure documentation is always updated for each phase/revision with the same title and content structure as the example in `docs/implementation/phase-04-rev01.md`.

## Working style
- Continue coding normally unless explicitly told to stop.
- Prefer small, focused changes that match the current phase and revision.
- Do not redesign unrelated parts of the project.
- Keep implementation aligned with the current phase document and architecture docs.
- Prefer minimal working implementations first, then improvements in later revisions.

## When implementing a task
When completing or significantly updating a phase/revision:
1. implement the code changes
2. update the matching file in `docs/implementation/`
3. keep the documentation short and practical
4. mention:
   - goal
   - decision why this approach was taken (if not obvious)
   - describe how this fits into the overall project direction and architecture
   - scope implemented
   - notes / follow-up items
   - Alternatives considered (if any) and why they were rejected
   - files changed

## Documentation rules
Implementation docs should stay concise and avoid bloated explanations.

Use this structure:

- Title
- Goal
- Key Decisions for this implementation, including any chat instructions and the reason i asked for changes.
- Architectural context (how this fits into the overall project direction and architecture)
- Flow Chart or Sequence Diagram (User interaction scenario or data flow)
- Scope implemented
- Files changed
- Notes
- Next step

## Scope control
- Do not add features from future phases unless explicitly requested.
- If a refactor is done, keep it inside the current phase/revision scope.
- If something is only scaffolding for the future, clearly label it as scaffolding.

## Project direction
This is a product-first habit tracker:
- FastAPI backend
- React frontend
- Postgres as source of truth
- pgvector for semantic features
- LangGraph for later multi-step AI orchestration
- future vision service must remain separate from core backend

## Code conventions

### Project structure
- `schemas/` — Pydantic model definitions only. What things **are** (shapes of data). No logic.
- `services/` — Business logic and state. What things **do**. Organized by feature subfolder: `services/sql/`, `services/chat/`, `services/embedding/`. Do not add new top-level service files; every new feature gets its own subfolder from the start.
- `api/` — FastAPI route handlers. Thin layer: validate input, call a service, return a response schema. No business logic here.
- `models/orm/` — SQLAlchemy ORM models. Single source of truth for table shape.
- `models/repository/` — Repository classes. DB access only; no business rules.
- `core/` — Application-wide constants and configuration. Values read from environment variables with sensible defaults. All tuneable constants (timeouts, row limits, batch sizes, etc.) live here — never as magic numbers scattered in service files.

### Class-based services
- Every service is a **class** (e.g. `class SqlExecutionService`). The class holds configuration and exposes instance methods.
- Configuration is injected at **construction time** via `__init__` parameters with defaults from `core/config.py`. This allows tests to override behaviour without patching globals.
- Each service module exposes exactly one **module-level singleton** (e.g. `sql_execution_service = SqlExecutionService()`). Callers import and use the singleton — never the class directly.
- Private helpers with no external dependencies are **static methods** (`@staticmethod`) or instance methods of the class. Module-level private functions are only acceptable when they are pure data-transformation utilities with no class dependency (e.g. regex helpers).

### Error handling
- Feature-specific exceptions live in a dedicated **`errors.py`** inside the feature subfolder (e.g. `services/sql/errors.py`).
- Every feature defines a **base exception class** (e.g. `class SqlError(Exception)`), with all feature exceptions inheriting from it. Callers can catch the whole family with one clause.
- Never define exception classes inside a service module. This avoids circular imports and keeps exception types importable independently.

### API schemas vs internal schemas
- **Public API schemas** (what the HTTP layer returns) live in `schemas/` and are returned by FastAPI endpoint functions. Keep these stable and versioned.
- **Internal pipeline schemas** (contracts between services) also live in `schemas/` but are clearly documented as internal. They are Pydantic models so they are typed, validated, and easy to log/serialize.
- Never return raw dicts or ORM objects from route handlers. Always use a typed schema.

### Constants and configuration
- All tuneable values (timeouts, row limits, batch sizes, window sizes) belong in `core/config.py`.
- Values are read from environment variables with a sensible default: `int(os.getenv("SQL_MAX_ROWS", "200"))`.
- Service files import from `core/config` — they never define magic numbers inline.

### Testing
- Test files mirror the source structure: `tests/habittracker/services/sql/` matches `services/sql/`.
- Unit tests mock all I/O (database sessions, HTTP calls, file access). No real infrastructure in unit tests.
- Tests call the **singleton instance** (e.g. `sql_execution_service.execute(...)`) to match production usage.
- Static methods on service classes can be called directly on the class in tests (e.g. `SqlExecutionService._validate_static(...)`).
- Each test class covers one behaviour area. Use `@pytest.mark.parametrize` for input variation.