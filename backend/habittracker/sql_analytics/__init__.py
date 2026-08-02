"""Generic SQL Analytics Core Package.

A reusable, application-agnostic library for safe SQL analytics generation,
validation, execution, and answer synthesis.

Core components:
- contracts: Pydantic models for all data structures
- catalog: Provider protocol and implementations
- renderer: Generic prompt rendering from catalog
- settings: Configuration constants

Applications provide their own SqlCatalogProvider implementation.
"""

from habittracker.sql_analytics.contracts import (
    SqlColumnDefinition,
    SqlTableDefinition,
    SqlRelationshipDefinition,
    SqlSchemaCatalog,
    SQLGenerationRequest,
    GeneratedSql,
    SqlValidationError,
    SqlValidationResult,
    SQLExecutionResult,
    SqlEvidenceItem,
    SqlAnswerResult,
)

from habittracker.sql_analytics.catalog import (
    SqlCatalogProvider,
    StaticSqlCatalogProvider,
    LazySqlCatalogProvider,
)

from habittracker.sql_analytics.renderer import (
    SqlSchemaContextRenderer,
    render_catalog_for_prompt,
)

from habittracker.sql_analytics.settings import (
    SqlAnalyticsSettings,
    get_settings,
)

__all__ = [
    # Contracts
    "SqlColumnDefinition",
    "SqlTableDefinition",
    "SqlRelationshipDefinition",
    "SqlSchemaCatalog",
    "SQLGenerationRequest",
    "GeneratedSql",
    "SqlValidationError",
    "SqlValidationResult",
    "SQLExecutionResult",
    "SqlEvidenceItem",
    "SqlAnswerResult",
    # Catalog
    "SqlCatalogProvider",
    "StaticSqlCatalogProvider",
    "LazySqlCatalogProvider",
    # Renderer
    "SqlSchemaContextRenderer",
    "render_catalog_for_prompt",
    # Settings
    "SqlAnalyticsSettings",
    "get_settings",
]

__version__ = "0.1.0"