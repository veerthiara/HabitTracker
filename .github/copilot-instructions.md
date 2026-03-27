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