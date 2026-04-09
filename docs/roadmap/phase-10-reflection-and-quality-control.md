# Phase 10 — Reflection and Quality Control

## Goal
Improve answer reliability by adding optional review/self-correction steps for difficult queries.

## Why
Not every question needs reflection, but SQL generation, weak evidence, and ambiguous analytical questions benefit from quality checks.

## Scope
- evidence sufficiency checks
- SQL repair loop
- answer review against evidence
- conditional retry/review path in LangGraph

## Out of scope
- always-on reflection for every request
- autonomous open-ended agents