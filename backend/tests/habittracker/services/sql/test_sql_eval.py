"""SQL evaluation harness — regression tests against the sql_eval_questions fixture.

Purpose
-------
This module provides a stable regression baseline for the text-to-SQL path.
It runs two categories of checks against every question in the fixture file:

  1. Intent classification — verify SqlIntentClassifier maps each question to
     the expected SqlAnalyticsIntent.  No LLM call; runs in milliseconds.

  2. Template SQL assertions — for every non-UNKNOWN question, render the SQL
     template using the fixture's template_params and assert:
       • expected tables appear in the SQL
       • expected columns appear in the SQL
       • must_not_contain patterns are absent
       • universal invariants hold (:user_id, LIMIT, SELECT)

The tests do NOT call the LLM or hit the database.  They exercise only the
deterministic parts of the pipeline (intent classifier + template renderer).
This makes the suite fast enough to run on every pull request.

Model-swap workflow
-------------------
To measure the impact of a model change (e.g. Llama 3.2 → Qwen 2.5 Coder):
  1. Change OLLAMA_CHAT_MODEL in core/config.py (or the env var).
  2. Run `make sql-eval` — the intent and template tests should still pass
     because they are model-independent.
  3. Add LLM-backed eval cases to the fixture and a separate test class
     (TestLlmSqlAssertions) if you need to measure SQL quality from the LLM
     fallback path.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from habittracker.schemas.sql_template import SqlAnalyticsIntent, SqlTemplateParams
from habittracker.services.sql.intent_classifier import sql_intent_classifier
from habittracker.services.sql.template_renderer import sql_template_renderer

# ── Fixture loading ───────────────────────────────────────────────────────────

_FIXTURE_PATH = (
    pathlib.Path(__file__).parent.parent.parent.parent  # tests/
    / "fixtures"
    / "sql_eval_questions.json"
)


def _load_cases() -> list[dict]:
    with _FIXTURE_PATH.open() as fh:
        return json.load(fh)


_CASES = _load_cases()


def _case_id(case: dict) -> str:
    return case["id"]


# ── Test classes ──────────────────────────────────────────────────────────────


class TestIntentClassification:
    """Verify that every fixture question routes to the expected intent.

    This test is model-independent — the classifier is keyword-based and
    never calls the LLM.  A failure here means either the question wording
    changed or the keyword set regressed.
    """

    @pytest.mark.parametrize("case", _CASES, ids=_case_id)
    def test_classifies_correctly(self, case: dict) -> None:
        result = sql_intent_classifier.classify(case["question"])
        expected = SqlAnalyticsIntent(case["expected_intent"])

        assert result == expected, (
            f"\nQuestion:  {case['question']!r}"
            f"\nExpected:  {expected.value!r}"
            f"\nGot:       {result.value!r}"
        )


class TestTemplateSqlAssertions:
    """Verify SQL structure for every template-backed fixture entry.

    Skips UNKNOWN-intent entries (no template to render) and entries
    without template_params.  For all others, renders the SQL and asserts:
      - each expected_table appears in the SQL text
      - each expected_column appears in the SQL text
      - no must_not_contain pattern appears in the SQL text
      - universal invariants: :user_id bind param, LIMIT, SELECT
    """

    @pytest.mark.parametrize("case", _CASES, ids=_case_id)
    def test_sql_structure(self, case: dict) -> None:
        if case["expected_intent"] == SqlAnalyticsIntent.UNKNOWN.value:
            pytest.skip("UNKNOWN intent — no template to render")

        if case.get("template_params") is None:
            pytest.skip("Fixture entry has no template_params")

        intent = SqlAnalyticsIntent(case["expected_intent"])
        params = SqlTemplateParams(intent=intent, **case["template_params"])
        sql = sql_template_renderer.render(params)

        # ── Expected tables ───────────────────────────────────────────────────
        for table in case.get("expected_tables", []):
            assert table in sql, (
                f"\nExpected table {table!r} missing from SQL:"
                f"\n  Question: {case['question']!r}"
                f"\n  SQL:      {sql}"
            )

        # ── Expected columns ──────────────────────────────────────────────────
        for col in case.get("expected_columns", []):
            assert col in sql, (
                f"\nExpected column {col!r} missing from SQL:"
                f"\n  Question: {case['question']!r}"
                f"\n  SQL:      {sql}"
            )

        # ── Forbidden patterns ────────────────────────────────────────────────
        for pattern in case.get("must_not_contain", []):
            assert pattern not in sql, (
                f"\nForbidden pattern {pattern!r} found in SQL:"
                f"\n  Question: {case['question']!r}"
                f"\n  SQL:      {sql}"
            )

        # ── Universal invariants ──────────────────────────────────────────────
        assert ":user_id" in sql, (
            f"\nuser_id bind param missing from SQL:"
            f"\n  Question: {case['question']!r}"
            f"\n  SQL:      {sql}"
        )
        assert "LIMIT" in sql.upper(), (
            f"\nLIMIT clause missing from SQL:"
            f"\n  Question: {case['question']!r}"
            f"\n  SQL:      {sql}"
        )
        assert sql.strip().upper().startswith("SELECT"), (
            f"\nSQL does not start with SELECT:"
            f"\n  Question: {case['question']!r}"
            f"\n  SQL:      {sql}"
        )
