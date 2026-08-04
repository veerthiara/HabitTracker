"""SQL Generation Prompt Builder.

Constructs provider messages for generating SQL from natural-language questions.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from habittracker.sql_analytics.contracts import SqlGenerationRequest


# ── System Prompt ──────────────────────────────────────────────────────────────

SQL_GENERATION_SYSTEM_PROMPT = """You are a SQL generation assistant for analytical queries.

Your task is to generate exactly ONE read-only PostgreSQL SELECT query based on:
1. The approved database schema below
2. The user's analytical question
3. The constraints listed at the end

The schema contains ONLY tables and columns approved for analytical use.
Any table or column not listed is forbidden.

CRITICAL RULES:
- Output MUST be valid JSON only — no markdown, no commentary
- Generate EXACTLY ONE SELECT statement (WITH ... SELECT is allowed)
- Use :user_id as a bound parameter for user-scoped filtering — NEVER embed the actual user ID
- Use only tables and columns from the approved schema
- No INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE
- No multiple statements
- No system schemas (pg_catalog, information_schema)
- No comments intended to bypass rules
- No direct user ID literals in SQL
- For row-list queries: include LIMIT (use a reasonable default like 100)
- Aggregation queries returning a single small result may omit LIMIT
- PostgreSQL syntax only
- The generated SQL is an UNTRUSTED CANDIDATE — it will be validated separately

JSON OUTPUT SHAPE (required):
{
  "sql": "SELECT ...",
  "referenced_tables": ["table_name"],
  "referenced_columns": ["table.column"],
  "explanation": "Short explanation of the query logic",
  "confidence": 0.0
}"""


# ── Prompt Builder ──────────────────────────────────────────────────────────────

def build_sql_generation_messages(request: "SqlGenerationRequest") -> tuple[dict[str, str], ...]:
    """Build the ordered message list for SQL generation.

    Args:
        request: SQLGenerationRequest containing question, user_id, schema_context,
                 and optional conversation_history.

    Returns:
        Tuple of message dicts (role, content) ready for ChatProvider.complete().
    """
    messages = [
        {"role": "system", "content": SQL_GENERATION_SYSTEM_PROMPT},
    ]

    # Add conversation history if provided (as user/assistant pairs)
    if request.conversation_history:
        for msg in request.conversation_history:
            role = msg.get("role")
            content = msg.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    # Add schema context + current question
    user_content = (
        f"Approved schema context:\n{request.schema_context}\n\n"
        f"User question: {request.question}\n\n"
        f"Bound parameter for user-scoped tables: :user_id\n\n"
        "Generate the JSON response now."
    )
    messages.append({"role": "user", "content": user_content})

    return tuple(messages)