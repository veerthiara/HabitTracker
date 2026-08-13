"""Tests for SQL Policy Validation Service - Phase 09 Rev 04.3."""

import pytest
from habittracker.sql_analytics.catalog import StaticSqlCatalogProvider
from habittracker.sql_analytics.contracts import (
    SqlPolicyValidationResult,
    SqlPolicyError,
    SqlSchemaCatalog,
    SqlTableDefinition,
    SqlColumnDefinition,
)
from habittracker.sql_analytics.policy import SqlPolicyValidationService
from habittracker.sql_analytics.settings import SqlAnalyticsSettings


# ── Commerce Catalog Fixture ───────────────────────────────────────────────────

def _commerce_catalog() -> SqlSchemaCatalog:
    """Generic commerce catalog for testing."""
    return SqlSchemaCatalog(
        catalog_name="commerce",
        catalog_version="1",
        dialect="postgresql",
        tables=(
            SqlTableDefinition(
                name="customers",
                description="Customer accounts",
                user_scoped=False,
                columns=(
                    SqlColumnDefinition(name="id", description="Customer ID", data_type="uuid", is_primary_key=True),
                    SqlColumnDefinition(name="account_id", description="Account ID", data_type="uuid", nullable=False),
                    SqlColumnDefinition(name="name", description="Customer name", data_type="varchar(255)", nullable=False),
                    SqlColumnDefinition(name="created_at", description="Account creation", data_type="timestamp with time zone", nullable=False),
                ),
            ),
            SqlTableDefinition(
                name="orders",
                description="Customer orders",
                user_scoped=True,
                scope_strategy="direct",
                columns=(
                    SqlColumnDefinition(name="id", description="Order ID", data_type="uuid", is_primary_key=True),
                    SqlColumnDefinition(name="account_id", description="Account ID", data_type="uuid", nullable=False, is_user_scope=True),
                    SqlColumnDefinition(name="customer_id", description="Buyer", data_type="uuid", is_foreign_key=True, foreign_key_target="customers.id"),
                    SqlColumnDefinition(name="total_cents", description="Order total in cents", data_type="integer", nullable=False),
                    SqlColumnDefinition(name="status", description="Order status", data_type="varchar(50)", nullable=False),
                    SqlColumnDefinition(name="placed_at", description="Order timestamp", data_type="timestamp with time zone", nullable=False),
                ),
            ),
            SqlTableDefinition(
                name="order_items",
                description="Order line items",
                user_scoped=True,
                scope_strategy="direct",
                columns=(
                    SqlColumnDefinition(name="id", description="Item ID", data_type="uuid", is_primary_key=True),
                    SqlColumnDefinition(name="account_id", description="Account ID", data_type="uuid", nullable=False, is_user_scope=True),
                    SqlColumnDefinition(name="order_id", description="Order reference", data_type="uuid", is_foreign_key=True, foreign_key_target="orders.id"),
                    SqlColumnDefinition(name="product_name", description="Product name", data_type="varchar(255)", nullable=False),
                    SqlColumnDefinition(name="quantity", description="Quantity", data_type="integer", nullable=False),
                    SqlColumnDefinition(name="unit_price_cents", description="Unit price in cents", data_type="integer", nullable=False),
                ),
            ),
        ),
        relationships=(),
        global_rules=(),
    )


# ── Test Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def catalog_provider():
    return StaticSqlCatalogProvider(_commerce_catalog())


@pytest.fixture
def policy_settings():
    return SqlAnalyticsSettings(
        required_scope_parameter="user_id",
        default_result_limit=50,
        max_result_limit=500,
    )


@pytest.fixture
def validation_service(catalog_provider, policy_settings):
    return SqlPolicyValidationService(catalog_provider=catalog_provider, settings=policy_settings)


# ── Test Basic Service (Rev 04.1) ──────────────────────────────────────────────

class TestSqlPolicyValidationService:
    """Basic service tests."""

    def test_basic_select_no_parameters(self, validation_service):
        """SELECT 1 -> valid=True, no parameters."""
        result = validation_service.validate("SELECT 1")
        assert result.valid is True
        assert result.detected_parameters == ()
        assert result.scoped_tables == ()
        assert result.effective_limit is None
        assert result.normalized_sql is not None

    def test_non_user_scoped_table_no_scope_required(self, validation_service):
        """Non-user-scoped table doesn't require scope."""
        result = validation_service.validate(
            "SELECT id FROM customers WHERE account_id = $1"
        )
        assert result.valid is True
        assert result.detected_parameters == ("1",)
        assert result.scoped_tables == ()

    def test_one_named_parameter(self, validation_service):
        """One named bind parameter -> detected."""
        result = validation_service.validate(
            "SELECT id FROM orders WHERE account_id = @user_id"
        )
        assert result.valid is True
        assert result.detected_parameters == ("user_id",)

    def test_several_parameters(self, validation_service):
        """Multiple bind parameters -> sorted tuple."""
        result = validation_service.validate(
            "SELECT id FROM orders WHERE account_id = @user_id AND status = @status"
        )
        assert result.valid is True
        assert result.detected_parameters == ("status", "user_id")

    def test_duplicate_parameter(self, validation_service):
        """Duplicate parameter appears only once."""
        result = validation_service.validate(
            "SELECT id FROM orders WHERE account_id = @user_id AND customer_id = @user_id"
        )
        assert result.valid is True
        assert result.detected_parameters == ("user_id",)

    def test_string_literal_is_not_parameter(self, validation_service):
        """String literal ':user_id' is not a parameter."""
        result = validation_service.validate(
            "SELECT ':user_id' AS label"
        )
        assert result.valid is True
        assert result.detected_parameters == ()

    def test_parameter_inside_string_literal(self, validation_service):
        """Parameter-looking text inside longer string is not detected."""
        result = validation_service.validate(
            "SELECT 'hello :user_id world' AS label"
        )
        assert result.valid is True
        assert result.detected_parameters == ()

    def test_wrong_parameter_still_detected(self, validation_service):
        """Wrong parameter name fails scope validation with USER_SCOPE_PARAMETER_REQUIRED."""
        result = validation_service.validate(
            "SELECT id FROM orders WHERE account_id = @other_id"
        )
        assert result.valid is False
        assert any(e.code == "USER_SCOPE_PARAMETER_REQUIRED" for e in result.errors)

    def test_alias_does_not_affect_parameter_detection(self, validation_service):
        """Table alias doesn't affect parameter detection."""
        result = validation_service.validate(
            "SELECT o.id FROM orders o WHERE o.account_id = @user_id"
        )
        assert result.valid is True
        assert result.detected_parameters == ("user_id",)

    def test_parameter_inside_cte_detected(self, validation_service):
        """Parameter inside a properly scoped CTE is detected."""
        result = validation_service.validate(
            "WITH x AS (SELECT id FROM orders WHERE account_id = @user_id) SELECT id FROM x"
        )
        assert result.valid is True
        assert result.detected_parameters == ("user_id",)
        assert result.scoped_tables == ("orders",)

    def test_parameter_inside_nested_subquery_detected(self, validation_service):
        """Parameter inside a properly scoped nested subquery is detected."""
        result = validation_service.validate(
            "SELECT c.name FROM customers c "
            "WHERE c.id IN (SELECT customer_id FROM orders WHERE account_id = @user_id)"
        )
        assert result.valid is True
        assert result.detected_parameters == ("user_id",)
        assert result.scoped_tables == ("orders",)

    def test_empty_sql(self, validation_service):
        """Empty SQL -> invalid with EMPTY_SQL."""
        result = validation_service.validate("")
        assert result.valid is False
        assert any(e.code == "EMPTY_SQL" for e in result.errors)

    def test_whitespace_only_sql(self, validation_service):
        """Whitespace-only SQL -> invalid with EMPTY_SQL."""
        result = validation_service.validate("   \n  ")
        assert result.valid is False
        assert any(e.code == "EMPTY_SQL" for e in result.errors)

    def test_malformed_sql(self, validation_service):
        """Malformed SQL -> invalid with PARSE_ERROR."""
        result = validation_service.validate("INVALID SQL")
        assert result.valid is False
        assert any(e.code == "PARSE_ERROR" for e in result.errors)

    def test_multiple_statements(self, validation_service):
        """Multiple statements -> invalid with MULTIPLE_STATEMENTS."""
        result = validation_service.validate("SELECT 1; SELECT 2")
        assert result.valid is False
        assert any(e.code == "MULTIPLE_STATEMENTS" for e in result.errors)

    def test_unsupported_dialect(self):
        """Unsupported catalog dialect -> invalid with UNSUPPORTED_DIALECT."""
        from habittracker.sql_analytics.contracts import SqlSchemaCatalog, SqlTableDefinition, SqlColumnDefinition
        from habittracker.sql_analytics.catalog import StaticSqlCatalogProvider

        bad_catalog = SqlSchemaCatalog(
            catalog_name="test",
            catalog_version="1",
            dialect="mysql",  # Unsupported
            tables=(
                SqlTableDefinition(name="t", description="x", columns=(
                    SqlColumnDefinition(name="id", description="x", data_type="int", is_primary_key=True),
                )),
            ),
        )
        service = SqlPolicyValidationService(catalog_provider=StaticSqlCatalogProvider(bad_catalog))
        result = service.validate("SELECT 1")
        assert result.valid is False
        assert any(e.code == "UNSUPPORTED_DIALECT" for e in result.errors)

    def test_deterministic_ordering(self, validation_service):
        """Detected parameters are deterministically sorted."""
        result = validation_service.validate(
            "SELECT * FROM orders WHERE a = @z AND b = @a AND c = @m"
        )
        params = list(result.detected_parameters)
        assert params == sorted(params)
        assert params == ["a", "m", "z"]

    def test_effective_limit_none(self, validation_service):
        """effective_limit is None in Rev 04."""
        result = validation_service.validate(
            "SELECT id FROM orders WHERE account_id = @user_id"
        )
        assert result.effective_limit is None

    def test_normalized_sql_present(self, validation_service):
        """Normalized SQL exists for successful parse."""
        result = validation_service.validate("SELECT id FROM orders WHERE account_id = @user_id")
        assert result.valid is True
        assert result.normalized_sql is not None
        assert "SELECT" in result.normalized_sql.upper()

    def test_input_not_mutated(self, validation_service):
        """Input SQL string is not mutated."""
        sql = "SELECT id FROM orders WHERE account_id = @user_id"
        original = sql
        validation_service.validate(sql)
        assert sql == original


# ── Test Policy Settings ──────────────────────────────────────────────────────────────

class TestPolicySettings:
    """Test policy settings are properly loaded."""

    def test_required_scope_parameter_default(self):
        """Default required_scope_parameter is user_id."""
        settings = SqlAnalyticsSettings()
        assert settings.required_scope_parameter == "user_id"

    def test_default_result_limit(self):
        """Default result limit is set."""
        settings = SqlAnalyticsSettings()
        assert settings.default_result_limit >= 1

    def test_max_result_limit(self):
        """Max result limit is set."""
        settings = SqlAnalyticsSettings()
        assert settings.max_result_limit >= settings.default_result_limit

    def test_env_override(self):
        """Settings can be overridden by providing values directly."""
        # Test direct instantiation with override
        settings = SqlAnalyticsSettings(required_scope_parameter="account_id")
        assert settings.required_scope_parameter == "account_id"


# ── Test Rev 04.2: Direct User-Scope Enforcement ────────────────────────────────

class TestDirectScopeEnforcement:
    """Tests for direct user-scope enforcement (Rev 04.2)."""

    def test_correct_direct_scope(self, validation_service):
        """Correct direct scope with @user_id is valid."""
        result = validation_service.validate(
            "SELECT id FROM orders WHERE account_id = @user_id"
        )
        assert result.valid is True
        assert result.scoped_tables == ("orders",)

    def test_alias_scope(self, validation_service):
        """Alias-qualified scope is valid."""
        result = validation_service.validate(
            "SELECT o.id FROM orders o WHERE o.account_id = @user_id"
        )
        assert result.valid is True
        assert result.scoped_tables == ("orders",)

    def test_reversed_equality(self, validation_service):
        """Reversed equality @user_id = account_id is valid."""
        result = validation_service.validate(
            "SELECT id FROM orders WHERE @user_id = account_id"
        )
        assert result.valid is True
        assert result.scoped_tables == ("orders",)

    def test_missing_scope(self, validation_service):
        """Missing scope predicate is rejected."""
        result = validation_service.validate(
            "SELECT id FROM orders"
        )
        assert result.valid is False
        assert any(e.code == "USER_SCOPE_REQUIRED" for e in result.errors)

    def test_wrong_column(self, validation_service):
        """Wrong column (not is_user_scope) does not satisfy scope."""
        result = validation_service.validate(
            "SELECT id FROM orders WHERE id = @user_id"
        )
        assert result.valid is False
        assert any(e.code == "USER_SCOPE_REQUIRED" for e in result.errors)

    def test_wrong_parameter(self, validation_service):
        """Wrong parameter name does not satisfy scope."""
        result = validation_service.validate(
            "SELECT id FROM orders WHERE account_id = @other_id"
        )
        assert result.valid is False
        assert any(e.code == "USER_SCOPE_PARAMETER_REQUIRED" for e in result.errors)

    def test_string_literal(self, validation_service):
        """String literal scope is rejected."""
        result = validation_service.validate(
            "SELECT id FROM orders WHERE account_id = 'abc'"
        )
        assert result.valid is False
        assert any(e.code == "USER_SCOPE_LITERAL_NOT_ALLOWED" for e in result.errors)

    def test_numeric_literal(self, validation_service):
        """Numeric literal scope is rejected."""
        result = validation_service.validate(
            "SELECT id FROM orders WHERE account_id = 123"
        )
        assert result.valid is False
        assert any(e.code == "USER_SCOPE_LITERAL_NOT_ALLOWED" for e in result.errors)

    def test_inequality(self, validation_service):
        """Inequality does not satisfy scope."""
        result = validation_service.validate(
            "SELECT id FROM orders WHERE account_id <> @user_id"
        )
        assert result.valid is False
        assert any(e.code in ("USER_SCOPE_REQUIRED", "USER_SCOPE_AMBIGUOUS") for e in result.errors)

    def test_and_predicate(self, validation_service):
        """Scope predicate under AND is valid."""
        result = validation_service.validate(
            "SELECT id FROM orders WHERE status = 'done' AND account_id = @user_id"
        )
        assert result.valid is True
        assert result.scoped_tables == ("orders",)

    def test_or_predicate(self, validation_service):
        """OR predicate is rejected conservatively."""
        result = validation_service.validate(
            "SELECT id FROM orders WHERE account_id = @user_id OR status = 'public'"
        )
        assert result.valid is False
        assert any(e.code == "USER_SCOPE_AMBIGUOUS" for e in result.errors)

    def test_non_user_scoped_table(self, validation_service):
        """Non-user-scoped table doesn't require scope."""
        result = validation_service.validate(
            "SELECT id FROM customers"
        )
        assert result.valid is True
        assert result.scoped_tables == ()

    def test_unsupported_strategy(self):
        """Unsupported scope strategy returns USER_SCOPE_UNSUPPORTED."""
        from habittracker.sql_analytics.contracts import SqlSchemaCatalog, SqlTableDefinition, SqlColumnDefinition
        from habittracker.sql_analytics.catalog import StaticSqlCatalogProvider

        catalog = SqlSchemaCatalog(
            catalog_name="test",
            catalog_version="1",
            dialect="postgresql",
            tables=(
                SqlTableDefinition(
                    name="data",
                    description="x",
                    user_scoped=True,
                    scope_strategy="relationship",  # Unsupported
                    columns=(
                        SqlColumnDefinition(name="id", description="x", data_type="uuid", is_primary_key=True, is_user_scope=True),
                    ),
                ),
            ),
        )
        service = SqlPolicyValidationService(catalog_provider=StaticSqlCatalogProvider(catalog))
        result = service.validate("SELECT id FROM data WHERE id = @user_id")
        assert result.valid is False
        assert any(e.code == "USER_SCOPE_UNSUPPORTED" for e in result.errors)

    def test_scoped_tables_deterministic(self, validation_service):
        """scoped_tables are deterministic and sorted."""
        result = validation_service.validate(
            "SELECT o.id, i.product_name FROM orders o "
            "JOIN order_items i ON i.order_id = o.id "
            "WHERE o.account_id = @user_id AND i.account_id = @user_id"
        )
        tables = list(result.scoped_tables)
        assert tables == sorted(tables)
        assert tables == ["order_items", "orders"]

    def test_detected_parameters_still_correct(self, validation_service):
        """detected_parameters still works with scope enforcement."""
        result = validation_service.validate(
            "SELECT id FROM orders WHERE account_id = @user_id AND status = @status"
        )
        assert result.valid is True
        assert result.detected_parameters == ("status", "user_id")

    def test_effective_limit_none(self, validation_service):
        """effective_limit remains None."""
        result = validation_service.validate(
            "SELECT id FROM orders WHERE account_id = @user_id"
        )
        assert result.effective_limit is None


class TestScopeTraversalRev043:
    """Rev 04.3 scope traversal and per-read enforcement."""

    def test_cte_valid_when_inner_physical_read_is_scoped(self, validation_service):
        result = validation_service.validate(
            "WITH scoped_orders AS ("
            "SELECT id FROM orders WHERE account_id = @user_id"
            ") "
            "SELECT id FROM scoped_orders"
        )
        assert result.valid is True
        assert result.scoped_tables == ("orders",)

    def test_cte_invalid_when_inner_physical_read_is_unscoped(self, validation_service):
        result = validation_service.validate(
            "WITH orders_cte AS (SELECT id FROM orders) SELECT id FROM orders_cte"
        )
        assert result.valid is False
        assert any(error.code == "USER_SCOPE_REQUIRED" for error in result.errors)

    def test_outer_filter_does_not_repair_inner_cte(self, validation_service):
        result = validation_service.validate(
            "WITH orders_cte AS (SELECT id, account_id FROM orders) "
            "SELECT id FROM orders_cte WHERE account_id = @user_id"
        )
        assert result.valid is False
        assert any(error.code == "USER_SCOPE_REQUIRED" for error in result.errors)

    def test_nested_subquery_valid_when_inner_read_is_scoped(self, validation_service):
        result = validation_service.validate(
            "SELECT c.name FROM customers c "
            "WHERE c.id IN ("
            "SELECT o.customer_id FROM orders o WHERE o.account_id = @user_id"
            ")"
        )
        assert result.valid is True
        assert result.scoped_tables == ("orders",)

    def test_nested_subquery_invalid_when_inner_read_is_unscoped(self, validation_service):
        result = validation_service.validate(
            "SELECT c.name FROM customers c "
            "WHERE c.id IN (SELECT o.customer_id FROM orders o)"
        )
        assert result.valid is False
        assert any(error.code == "USER_SCOPE_REQUIRED" for error in result.errors)

    def test_correlated_subquery_valid_when_inner_read_is_scoped(self, validation_service):
        result = validation_service.validate(
            "SELECT c.name FROM customers c "
            "WHERE EXISTS ("
            "SELECT 1 FROM orders o "
            "WHERE o.customer_id = c.id AND o.account_id = @user_id"
            ")"
        )
        assert result.valid is True
        assert result.scoped_tables == ("orders",)

    def test_correlated_subquery_invalid_when_scope_predicate_missing(self, validation_service):
        result = validation_service.validate(
            "SELECT c.name FROM customers c "
            "WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)"
        )
        assert result.valid is False
        assert any(error.code == "USER_SCOPE_REQUIRED" for error in result.errors)

    def test_same_physical_table_in_multiple_scopes_requires_each_read_to_be_scoped(self, validation_service):
        result = validation_service.validate(
            "SELECT o.id FROM orders o "
            "WHERE o.account_id = @user_id "
            "AND EXISTS (SELECT 1 FROM orders o2 WHERE o2.customer_id = o.customer_id)"
        )
        assert result.valid is False
        assert any(error.code == "USER_SCOPE_REQUIRED" for error in result.errors)

    def test_same_physical_table_in_multiple_scopes_is_valid_when_each_read_is_scoped(self, validation_service):
        result = validation_service.validate(
            "SELECT o.id FROM orders o "
            "WHERE o.account_id = @user_id "
            "AND EXISTS ("
            "SELECT 1 FROM orders o2 "
            "WHERE o2.customer_id = o.customer_id AND o2.account_id = @user_id"
            ")"
        )
        assert result.valid is True
        assert result.scoped_tables == ("orders",)

    def test_multiple_user_scoped_tables_require_independent_scope(self, validation_service):
        result = validation_service.validate(
            "SELECT o.id, i.product_name FROM orders o "
            "JOIN order_items i ON i.order_id = o.id "
            "WHERE o.account_id = @user_id"
        )
        assert result.valid is False
        assert any(error.code == "USER_SCOPE_REQUIRED" and error.context == "order_items" for error in result.errors)

    def test_multiple_user_scoped_tables_valid_when_each_is_scoped(self, validation_service):
        result = validation_service.validate(
            "SELECT o.id, i.product_name FROM orders o "
            "JOIN order_items i ON i.order_id = o.id "
            "WHERE o.account_id = @user_id AND i.account_id = @user_id"
        )
        assert result.valid is True
        assert result.scoped_tables == ("order_items", "orders")

    def test_scope_local_alias_reuse_is_resolved_per_scope(self, validation_service):
        result = validation_service.validate(
            "SELECT o.id FROM orders o "
            "WHERE o.account_id = @user_id "
            "AND EXISTS ("
            "SELECT 1 FROM order_items o "
            "WHERE o.order_id = outer_o.id AND o.account_id = @user_id"
            ")"
            .replace("outer_o", "o")
        )
        assert result.valid is True
        assert result.scoped_tables == ("order_items", "orders")
