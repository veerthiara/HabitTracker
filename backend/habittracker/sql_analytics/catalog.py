"""Catalog Provider Abstraction.

Defines the protocol for providing an SqlSchemaCatalog to the generic SQL analytics core.
Applications implement this protocol to supply their own catalog.
"""

from collections.abc import Callable
from typing import Protocol
from habittracker.sql_analytics.contracts import SqlSchemaCatalog


class SqlCatalogProvider(Protocol):
    """Protocol for providing an approved schema catalog.

    Applications implement this to supply their domain-specific catalog.
    The generic core depends only on this protocol, not on any implementation.
    """

    def get_catalog(self) -> SqlSchemaCatalog:
        """Return the approved schema catalog for this application.

        Returns:
            SqlSchemaCatalog: Complete catalog with tables, relationships, rules.
        """
        ...


class StaticSqlCatalogProvider:
    """Simple provider that returns a pre-built catalog.

    Useful for testing or when the catalog is statically defined.
    """

    def __init__(self, catalog: SqlSchemaCatalog) -> None:
        self._catalog = catalog

    def get_catalog(self) -> SqlSchemaCatalog:
        return self._catalog


# Optional: lazy-loading provider for expensive catalog construction
class LazySqlCatalogProvider:
    """Provider that builds the catalog on first access."""

    def __init__(self, factory: Callable[[], SqlSchemaCatalog]) -> None:
        self._factory = factory
        self._catalog: SqlSchemaCatalog | None = None

    def get_catalog(self) -> SqlSchemaCatalog:
        if self._catalog is None:
            self._catalog = self._factory()
        return self._catalog