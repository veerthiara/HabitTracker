"""SQL schema service.

Provides a compact, LLM-friendly schema summary for the approved tables that
the SQL analytics path is allowed to query.

Design decisions:
  - Only the tables listed in ALLOWED_TABLES may appear in generated SQL.
  - Column descriptions are written in business terms, not database terms,
    so the LLM can map natural language to the right column without guessing.
  - The schema summary is a plain string: easy to inject into any prompt
    without additional serialisation.
  - Daily summaries are excluded from SQL analytics — they are free-text
    blobs and are better served by the semantic retrieval path.
"""

from __future__ import annotations

# Tables the SQL analytics path is permitted to query.
ALLOWED_TABLES: frozenset[str] = frozenset(
    {
        "users",
        "habits",
        "habit_logs",
        "bottle_events",
        "notes",
    }
)

# Compact schema summary injected into SQL-generation prompts.
# Keep this in sync with the actual migrations if columns change.
SCHEMA_SUMMARY: str = """
Database: PostgreSQL
Timezone: all timestamps are stored with timezone (timestamptz). Use DATE() or AT TIME ZONE to work with dates.

Tables you MAY query (SELECT only):

users
  id          UUID  primary key
  created_at  TIMESTAMPTZ

habits
  id          UUID  primary key
  user_id     UUID  foreign key → users.id
  name        TEXT  habit name as entered by the user
  description TEXT  optional longer description
  frequency   TEXT  one of: 'daily', 'weekly', 'custom'
  is_active   BOOL  false means the habit has been archived
  created_at  TIMESTAMPTZ
  updated_at  TIMESTAMPTZ

habit_logs  (one row = one completion of a habit on a date)
  id          UUID  primary key
  habit_id    UUID  foreign key → habits.id
  user_id     UUID  foreign key → users.id
  logged_date DATE  the calendar date the habit was completed (no time component)
  notes       TEXT  optional free-text note attached to this log entry
  created_at  TIMESTAMPTZ

bottle_events  (one row = one bottle/drink recorded by the user)
  id          UUID  primary key
  user_id     UUID  foreign key → users.id
  event_ts    TIMESTAMPTZ  exact moment the bottle event was recorded
  volume_ml   INTEGER  liquid volume in millilitres for this event
  notes       TEXT  optional free-text note
  created_at  TIMESTAMPTZ

notes  (free-text journal entries written by the user)
  id          UUID  primary key
  user_id     UUID  foreign key → users.id
  content     TEXT  full text of the note
  created_at  TIMESTAMPTZ
  updated_at  TIMESTAMPTZ

Relationships:
  habits.user_id       → users.id
  habit_logs.habit_id  → habits.id
  habit_logs.user_id   → users.id
  bottle_events.user_id → users.id
  notes.user_id        → users.id

Important constraints:
  - Always filter by user_id using the provided :user_id parameter.
  - Never query tables not listed above.
  - Only SELECT statements are permitted.
  - Keep result sets small: add LIMIT unless the question explicitly asks for all data.
"""


def get_schema_summary() -> str:
    """Return the compact schema summary string for prompt injection."""
    return SCHEMA_SUMMARY.strip()


def is_table_allowed(table_name: str) -> bool:
    """Return True if the table name is in the approved list."""
    return table_name.lower() in ALLOWED_TABLES
