# Phase 09 — SQL Question Answering

## Goal
Allow the assistant to answer flexible analytical questions by generating safe read-only SQL against the app database.

## Why
The current repository-based flow handles known question types well, but it does not support broad ad hoc analytical questions.

## Scope
- schema-aware SQL generation
- read-only SQL execution
- validation and safety guardrails
- integration into LangGraph routing
- answer generation from SQL results

## Out of scope
- write queries
- arbitrary unrestricted SQL
- automatic schema modification