"""HabitTracker SQL Catalog Adapter.

Application-specific implementation of the approved schema catalog.
Contains HabitTracker table definitions derived from actual SQLAlchemy ORM metadata.

This module knows about HabitTracker's domain (habits, hydration, notes).
The generic sql_analytics core knows nothing about these.
"""

from habittracker.sql_analytics.contracts import (
    SqlColumnDefinition,
    SqlTableDefinition,
    SqlRelationshipDefinition,
    SqlSchemaCatalog,
)
from habittracker.sql_analytics.catalog import StaticSqlCatalogProvider
from habittracker.sql_analytics.settings import get_settings


# ── Column Factories ──────────────────────────────────────────────────────────

def pk(name: str, description: str, data_type: str = "uuid") -> SqlColumnDefinition:
    return SqlColumnDefinition(
        name=name,
        description=description,
        data_type=data_type,
        nullable=False,
        is_primary_key=True,
    )


def fk(name: str, description: str, target: str, data_type: str = "uuid") -> SqlColumnDefinition:
    return SqlColumnDefinition(
        name=name,
        description=description,
        data_type=data_type,
        nullable=False,
        is_foreign_key=True,
        foreign_key_target=target,
    )


def user_scope_col(name: str, description: str, data_type: str = "uuid") -> SqlColumnDefinition:
    return SqlColumnDefinition(
        name=name,
        description=description,
        data_type=data_type,
        nullable=False,
        is_user_scope=True,
        is_foreign_key=True,
        foreign_key_target="users.id",
    )


def col(name: str, description: str, data_type: str, nullable: bool = True, **kwargs) -> SqlColumnDefinition:
    return SqlColumnDefinition(
        name=name,
        description=description,
        data_type=data_type,
        nullable=nullable,
        **kwargs,
    )


def sensitive_col(name: str, description: str, data_type: str) -> SqlColumnDefinition:
    return SqlColumnDefinition(
        name=name,
        description=description,
        data_type=data_type,
        nullable=True,
        sensitive=True,
        allowed_for_select=False,
    )


# ── Table Definitions (derived from actual ORM metadata) ──────────────────────

def build_users_table() -> SqlTableDefinition:
    """users table from habittracker.models.orm.habittracker.user.User

    Included in catalog because other tables reference it via foreign keys.
    The authenticated user ID comes from application context, but the table
    is needed for relationship metadata.
    """
    return SqlTableDefinition(
        name="users",
        description="Application users. Each user owns all habit, hydration, and note data.",
        columns=(
            pk("id", "Unique user identifier"),
            col("created_at", "Account creation timestamp", "timestamp with time zone", nullable=False),
            col("updated_at", "Last profile update timestamp", "timestamp with time zone", nullable=False),
        ),
        user_scoped=False,
        allowed_for_select=False,  # Not for direct analytical queries
        business_rules=(
            "Root entity — all other user-scoped tables reference this via user_id",
        ),
    )


def build_habits_table() -> SqlTableDefinition:
    """habits table from habittracker.models.orm.habittracker.habit.Habit"""
    return SqlTableDefinition(
        name="habits",
        description="Habit definitions created by the user. Each habit has a frequency (daily/weekly/custom) and active status.",
        columns=(
            pk("id", "Unique habit identifier"),
            user_scope_col("user_id", "Owner user ID"),
            col("name", "Habit name (e.g., 'Morning run', 'Read 20 minutes')", "varchar(255)", nullable=False),
            col("description", "Optional habit description", "text"),
            col("frequency", "Recurrence: 'daily', 'weekly', or 'custom'", "varchar(50)", nullable=False),
            col("is_active", "Whether the habit is currently tracked", "boolean", nullable=False),
            col("created_at", "Habit creation timestamp", "timestamp with time zone", nullable=False),
            col("updated_at", "Last habit update timestamp", "timestamp with time zone", nullable=False),
        ),
        user_scoped=True,
        allowed_for_select=True,
        business_rules=(
            "Only active habits (is_active=true) should be considered for current tracking",
            "Frequency values: daily, weekly, custom",
        ),
    )


def build_habit_logs_table() -> SqlTableDefinition:
    """habit_logs table from habittracker.models.orm.habittracker.habit_log.HabitLog"""
    return SqlTableDefinition(
        name="habit_logs",
        description="Daily completion records for habits. One row per habit per day when marked complete. Use for streak analysis, completion rates, and trend queries.",
        columns=(
            pk("id", "Unique log entry identifier"),
            fk("habit_id", "Reference to the habit", "habits.id"),
            user_scope_col("user_id", "Owner user ID (denormalized for query convenience)"),
            col("logged_date", "Calendar date the habit was completed (UTC)", "date", nullable=False),
            col("notes", "Optional free-text notes for this completion", "text"),
            col("created_at", "Log entry creation timestamp", "timestamp with time zone", nullable=False),
        ),
        user_scoped=True,
        allowed_for_select=True,
        business_rules=(
            "One row per habit per date — unique constraint on (habit_id, logged_date)",
            "logged_date uses UTC calendar date",
            "habit logs represent completed habits",
        ),
    )


def build_bottle_events_table() -> SqlTableDefinition:
    """bottle_events table from habittracker.models.orm.habittracker.bottle_event.BottleEvent"""
    return SqlTableDefinition(
        name="bottle_events",
        description="Hydration tracking events. Each row records a bottle pickup with volume in milliliters and timestamp. Use for daily totals, hourly patterns, and trend analysis.",
        columns=(
            pk("id", "Unique event identifier"),
            user_scope_col("user_id", "Owner user ID"),
            col("event_ts", "Exact timestamp of the bottle pickup (UTC)", "timestamp with time zone", nullable=False),
            col("volume_ml", "Volume consumed in milliliters", "integer", nullable=False),
            col("notes", "Optional free-text notes for this event", "text"),
            col("created_at", "Event record creation timestamp", "timestamp with time zone", nullable=False),
        ),
        user_scoped=True,
        allowed_for_select=True,
        business_rules=(
            "Volume in milliliters (integer)",
            "event_ts is full timestamp with timezone — use date_trunc for daily grouping",
            "bottle events represent hydration activity",
        ),
    )


def build_daily_summaries_table() -> SqlTableDefinition:
    """daily_summaries table from habittracker.models.orm.habittracker.daily_summary.DailySummary"""
    return SqlTableDefinition(
        name="daily_summaries",
        description="Pre-computed daily summaries generated by the application. Contains aggregated metrics and AI-generated narrative summaries. Use for quick historical overviews without re-aggregating.",
        columns=(
            pk("id", "Unique summary identifier"),
            user_scope_col("user_id", "Owner user ID"),
            col("summary_date", "Calendar date this summary covers (UTC)", "date", nullable=False),
            col("content", "Full narrative summary text (may include AI-generated insights)", "text", nullable=False),
            col("created_at", "Summary creation timestamp", "timestamp with time zone", nullable=False),
            col("updated_at", "Last summary update timestamp", "timestamp with time zone", nullable=False),
        ),
        user_scoped=True,
        allowed_for_select=True,
        business_rules=(
            "One row per user per date",
            "Content may contain AI-generated narrative — treat as pre-computed summary",
            "daily summaries are precomputed",
        ),
    )


def build_notes_table() -> SqlTableDefinition:
    """notes table from habittracker.models.orm.habittracker.note.Note

    The embedding column is excluded entirely from the approved catalog per policy.
    Note content is exposed only when SQL_QA_ALLOW_NOTE_CONTENT=true.
    Semantic retrieval remains the preferred path for note meaning.
    """
    settings = get_settings()
    columns = [
        pk("id", "Unique note identifier"),
        user_scope_col("user_id", "Owner user ID"),
        col("source", "Origin: 'manual' (user-written) or 'ai' (AI-generated summary)", "varchar(50)", nullable=False),
        col("created_at", "Note creation timestamp", "timestamp with time zone", nullable=False),
        col("updated_at", "Last note update timestamp", "timestamp with time zone", nullable=False),
    ]

    if settings.allow_note_content:
        columns.append(col("content", "Note content text", "text", nullable=False))

    # Embedding column is NEVER included - sensitive, internal use only
    # excluded entirely from approved catalog

    return SqlTableDefinition(
        name="notes",
        description="User journal notes. Can be manually written or AI-generated. Contains pgvector embeddings for semantic search (internal only). Use for qualitative pattern analysis when combined with structured data.",
        columns=tuple(columns),
        user_scoped=True,
        allowed_for_select=True,
        business_rules=(
            "Source values: 'manual' or 'ai'",
            "Embedding column is internal only — not exposed in approved catalog",
            "Semantic retrieval via pgvector is the preferred path for note meaning",
        ),
    )


# ── Relationships (from actual ORM foreign keys) ──────────────────────────────

def build_relationships() -> tuple[SqlRelationshipDefinition, ...]:
    return (
        SqlRelationshipDefinition(
            left_table="habits",
            left_column="user_id",
            right_table="users",
            right_column="id",
            relationship_type="many_to_one",
            description="Habits belong to a user",
        ),
        SqlRelationshipDefinition(
            left_table="habit_logs",
            left_column="habit_id",
            right_table="habits",
            right_column="id",
            relationship_type="many_to_one",
            description="Log entries belong to a habit",
        ),
        SqlRelationshipDefinition(
            left_table="habit_logs",
            left_column="user_id",
            right_table="users",
            right_column="id",
            relationship_type="many_to_one",
            description="Log entries belong to a user (denormalized)",
        ),
        SqlRelationshipDefinition(
            left_table="bottle_events",
            left_column="user_id",
            right_table="users",
            right_column="id",
            relationship_type="many_to_one",
            description="Bottle events belong to a user",
        ),
        SqlRelationshipDefinition(
            left_table="daily_summaries",
            left_column="user_id",
            right_table="users",
            right_column="id",
            relationship_type="many_to_one",
            description="Daily summaries belong to a user",
        ),
        SqlRelationshipDefinition(
            left_table="notes",
            left_column="user_id",
            right_table="users",
            right_column="id",
            relationship_type="many_to_one",
            description="Notes belong to a user",
        ),
    )


# ── Catalog Builder ───────────────────────────────────────────────────────────

def build_habittracker_catalog() -> SqlSchemaCatalog:
    """Build the complete HabitTracker approved schema catalog."""
    return SqlSchemaCatalog(
        catalog_name="habittracker",
        catalog_version="1.0",
        dialect="postgresql",
        tables=(
            build_users_table(),
            build_habits_table(),
            build_habit_logs_table(),
            build_bottle_events_table(),
            build_daily_summaries_table(),
            build_notes_table(),
        ),
        relationships=build_relationships(),
        global_rules=(
            "Only SELECT statements allowed",
            "Always filter by user_id for data isolation on user-scoped tables",
            "Use LIMIT (default 50, max 100)",
            "No subqueries in FROM clause — use CTEs (WITH ...) instead",
            "No functions with side effects",
            "Date arithmetic: use CURRENT_DATE for 'today' (UTC)",
            "Cast types explicitly when needed: col::type",
            "Timestamps are stored in UTC",
        ),
    )


# ── Provider ──────────────────────────────────────────────────────────────────

class HabitTrackerSqlCatalogProvider(StaticSqlCatalogProvider):
    """HabitTracker-specific catalog provider.

    Implements SqlCatalogProvider protocol for dependency injection.
    """

    def __init__(self) -> None:
        super().__init__(build_habittracker_catalog())


# Convenience function for direct access
def get_habittracker_catalog() -> SqlSchemaCatalog:
    return build_habittracker_catalog()