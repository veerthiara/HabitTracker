"""Generic SQL Analytics Core Package.

A reusable, application-agnostic library for safe SQL analytics generation,
validation, execution, and answer synthesis.

Core components:
- contracts: Pydantic models for all data structures
- catalog: Provider protocol and implementations
- renderer: Generic prompt rendering from catalog
- settings: Configuration constants
- prompts: SQL generation prompt building
- generation: SqlGenerationService for converting NL to SQL

Applications provide their own SqlCatalogProvider implementation.
"""

# Contracts - exported directly (loads contracts.py completely first)
from habittracker.sql_analytics.contracts import (
    SqlColumnDefinition,
    SqlTableDefinition,
    SqlRelationshipDefinition,
    SqlSchemaCatalog,
    SqlGenerationRequest,
    GeneratedSql,
    SqlValidationError,
    SqlValidationResult,
    SqlExecutionResult,
    SqlEvidenceItem,
    SqlAnswerResult,
)

# Catalog - exported directly
from habittracker.sql_analytics.catalog import (
    SqlCatalogProvider,
    StaticSqlCatalogProvider,
    LazySqlCatalogProvider,
)

# Renderer - exported directly
from habittracker.sql_analytics.renderer import (
    SqlSchemaContextRenderer,
    render_catalog_for_prompt,
)

# Settings - exported directly
from habittracker.sql_analytics.settings import (
    SqlAnalyticsSettings,
    get_settings,
)

# Now import submodules that depend on contracts (after contracts are fully loaded)
from habittracker.sql_analytics.prompts import build_sql_generation_messages
from habittracker.sql_analytics.generation import (
    SqlGenerationService,
    SqlGenerationError,
    SqlGenerationResponseError,
)
from habittracker.sql_analytics.validation import SqlValidationService
from habittracker.sql_analytics.exceptions import SqlValidationException, SqlParseError
from habittracker.sql_analytics.policy import SqlPolicyValidationService
from habittracker.sql_analytics.contracts import SqlPolicyValidationResult, SqlPolicyError

__all__ = [
    # Contracts
    "SqlColumnDefinition",
    "SqlTableDefinition",
    "SqlRelationshipDefinition",
    "SqlSchemaCatalog",
    "SqlGenerationRequest",
    "GeneratedSql",
    "SqlValidationError",
    "SqlValidationResult",
    "SqlExecutionResult",
    "SqlEvidenceItem",
    "SqlAnswerResult",
    "SqlPolicyError",
    "SqlPolicyValidationResult",
    # Catalog
    "SqlCatalogProvider",
    "StaticSqlCatalogProvider",
    "LazySqlCatalogProvider",
    # Generation
    "SqlGenerationService",
    "SqlGenerationError",
    "SqlGenerationResponseError",
    "build_sql_generation_messages",
    # Renderer
    "SqlSchemaContextRenderer",
    "render_catalog_for_prompt",
    # Settings
    "SqlAnalyticsSettings",
    "get_settings",
    # Validation
    "SqlValidationService",
    "SqlValidationException",
    "SqlParseError",
    # Policy
    "SqlPolicyValidationService",
]

__version__ = "0.1.0"