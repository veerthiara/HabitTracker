# Phase 09 Rev 03 — SQL Validation Service

## Summary

This revision implements the reusable SQL validation layer for the SQL analytics pipeline. The validator parses generated SQL with SQLGlot, enforces the approved catalog allow-list, and returns parser-derived metadata without executing SQL.

Rev 03 remains intentionally limited to validation only. It does not execute SQL, enforce user-scope predicates, enforce `LIMIT`, modify LangGraph, or change the API surface.

## Parsing And Statement Support

- SQL is parsed with SQLGlot using the catalog dialect mapping:
  - `postgresql` -> `postgres`
  - `postgres` -> `postgres`
- Only a single statement is allowed.
- Supported read-only roots:
  - `SELECT`
  - `WITH ... SELECT`
  - `UNION`
  - `UNION ALL`
  - `WITH ... UNION`
- Multiple statements are rejected.
- Write, DDL, admin, and other non-read-only statements are rejected.
- Unsupported catalog dialects return `UNSUPPORTED_DIALECT`.

## Scope Analysis

Rev 03 uses SQLGlot scope traversal rather than string matching to validate tables and columns.

- `traverse_scope(...)` is used to inspect query scopes.
- Scope-aware selected sources distinguish:
  - physical catalog tables
  - CTE sources
  - derived tables / subqueries
- CTE visibility is determined from the active scope and its selected sources.
- Nested CTE names do not leak into unrelated scopes.
- Correlated subqueries continue to resolve outer references through enclosing scopes.

## Approved Table Validation

- Physical tables are collected from scope-selected sources only.
- Every physical table must exist in the approved catalog.
- Hidden tables (`allowed_for_select=False`) are rejected.
- Referenced tables are returned in canonical sorted order.

## Approved Column Validation

- Qualified columns are validated against the selected source visible in that scope.
- Unqualified columns are resolved against visible physical tables and visible CTE outputs.
- Ambiguous unqualified columns return `UNQUALIFIED_COLUMN_AMBIGUOUS`.
- Unknown columns return `COLUMN_NOT_ALLOWED`.
- Derived-table outputs must still be referenced through their alias.

## Physical-Column Reference Metadata

`SqlValidationResult.referenced_columns` contains only canonical approved physical catalog columns when lineage can be proven safely.

- Physical table references are returned as `table.column`.
- CTE and derived-table output references are traced back to physical columns when possible.
- Synthetic internal identifiers such as `cte:...` and `derived:...` are not returned.
- If a projected output is valid but has no provable physical lineage, it is accepted without inventing physical metadata.

## CTE And Derived-Table Handling

- CTE output columns are validated via SQLGlot scope-selected sources.
- Derived-table output columns are validated via the child scope's projected outputs.
- Aliased physical columns preserve physical lineage.
- Expressions and aggregates contribute lineage only through the physical columns they actually reference.

## Wildcards And COUNT(*)

- `SELECT *`, `table.*`, and `alias.*` are rejected.
- `COUNT(*)` is the one wildcard exception and remains allowed.

## Dangerous Functions And System Schemas

Blocked system schemas:

- `pg_catalog`
- `information_schema`
- `pg_toast`
- `pg_temp`
- `pg_internal`

Blocked dangerous functions:

- `pg_sleep`
- `pg_terminate_backend`
- `pg_cancel_backend`
- `dblink_connect`
- `lo_import`
- `lo_export`
- `pg_read_file`
- `pg_read_binary_file`

## Metadata Mismatch Warnings

When validation receives a `GeneratedSql` payload:

- model-reported tables are compared with parser-derived tables
- model-reported columns are compared with parser-derived columns
- mismatches produce warnings, not hard validation failures
- parser-derived metadata always wins in the returned result

## Dialect Handling

- The catalog dialect is the source of truth for parsing and normalization.
- Unsupported dialects fail validation early.
- Normalized SQL is rendered through SQLGlot when parsing and validation succeed far enough to support normalization.

## Parser Limitations

Current SQLGlot parser limitations are documented and tested as validation failures, including cases such as:

- write statements inside CTEs that SQLGlot cannot parse
- `SELECT ... FOR UPDATE`
- `SELECT ... INTO`
- other unsupported PostgreSQL constructs that surface as parse errors

These limitations are documented behavior, not silent pass-through.

## Deferred To Rev 04

The following are explicitly deferred and not implemented in Rev 03:

- SQL execution
- user-scope enforcement
- `LIMIT` / result-bound enforcement
- LangGraph integration changes
- API changes
