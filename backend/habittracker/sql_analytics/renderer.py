"""Generic Prompt Renderer.

Renders an SqlSchemaCatalog into a prompt-ready string for LLM context.
Zero knowledge of application-specific table names.
"""

from habittracker.sql_analytics.contracts import SqlSchemaCatalog, SqlTableDefinition, SqlColumnDefinition, SqlRelationshipDefinition


class SqlSchemaContextRenderer:
    """Renders an approved schema catalog into a deterministic prompt string."""

    def __init__(self) -> None:
        pass

    def render(self, catalog: SqlSchemaCatalog) -> str:
        """Render the complete catalog as a prompt-ready string.

        Args:
            catalog: The approved schema catalog to render.

        Returns:
            Formatted string suitable for injection into LLM prompts.
        """
        lines = [
            f"Database dialect: {catalog.dialect}",
            f"Catalog: {catalog.catalog_name} v{catalog.catalog_version}",
            "",
        ]

        # Tables - sorted by name for deterministic output
        selectable_tables = sorted(
            [t for t in catalog.tables if t.allowed_for_select],
            key=lambda t: t.name
        )

        for table in selectable_tables:
            lines.append(f"Table: {table.name}")
            if table.description:
                lines.append(f"Purpose: {table.description}.")
            if table.user_scoped:
                lines.append("User scoped: yes")
            else:
                lines.append("User scoped: no")

            if table.business_rules:
                for rule in table.business_rules:
                    lines.append(f"Business rule: {rule}")

            lines.append("Columns:")
            # Sort columns by name for deterministic output
            selectable_cols = sorted(table.selectable_columns(), key=lambda c: c.name)
            for col in selectable_cols:
                parts = [f"- {col.name} ({col.data_type})"]
                if col.is_primary_key:
                    parts.append("primary key")
                if col.is_foreign_key:
                    # Only render FK target if the target table is allowed_for_select
                    fk_target_table = col.foreign_key_target.split(".")[0] if col.foreign_key_target else None
                    if fk_target_table:
                        try:
                            target_table = catalog.get_table(fk_target_table)
                            if target_table.allowed_for_select:
                                parts.append(f"foreign key -> {col.foreign_key_target}")
                        except KeyError:
                            pass  # Target table not in catalog
                if col.is_user_scope:
                    parts.append("user scope")
                if not col.nullable:
                    parts.append("not null")
                parts.append(col.description + ".")
                lines.append(" ".join(parts))
            lines.append("")

        # Relationships - sorted for deterministic output
        if catalog.relationships:
            lines.append("Relationships:")
            sorted_rels = sorted(
                catalog.relationships,
                key=lambda r: (r.left_table, r.left_column, r.right_table, r.right_column)
            )
            for rel in sorted_rels:
                left = catalog.get_table(rel.left_table)
                right = catalog.get_table(rel.right_table)
                if not left.allowed_for_select or not right.allowed_for_select:
                    continue
                type_label = {
                    "one_to_one": "one-to-one",
                    "one_to_many": "one-to-many",
                    "many_to_one": "many-to-one",
                    "many_to_many": "many-to-many",
                }.get(rel.relationship_type, rel.relationship_type)
                lines.append(
                    f"- {rel.left_table}.{rel.left_column} -> {rel.right_table}.{rel.right_column} ({type_label})"
                )
                if rel.description:
                    lines.append(f"  -- {rel.description}")
            lines.append("")

        # Global rules
        if catalog.global_rules:
            lines.append("Global rules:")
            for rule in catalog.global_rules:
                lines.append(f"- {rule}")
            lines.append("")

        return "\n".join(lines).strip()


def render_catalog_for_prompt(catalog: SqlSchemaCatalog) -> str:
    """Convenience function for backward compatibility."""
    renderer = SqlSchemaContextRenderer()
    return renderer.render(catalog)