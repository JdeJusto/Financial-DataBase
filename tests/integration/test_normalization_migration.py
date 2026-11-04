"""Migration/contract tests for the v0.2 normalization layer.

These run against the test database after ``financial_database.cli migrate``.
They do not insert production facts: they validate the catalog, the seeded
mapping and the idempotence/rollback of migration 0022.
"""

from __future__ import annotations

from pathlib import Path

import psycopg

MIGRATION = (
    Path(__file__).resolve().parents[2] / "db" / "migrations"
    / "0022_normalization_v0.2.sql"
)


def _columns(cur, relation: str) -> set[str]:
    cur.execute(f"SELECT * FROM {relation} LIMIT 0")
    return {column.name for column in cur.description}


def test_mapping_table_populated(db_connection):
    with db_connection.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM concept_normalization")
        assert cur.fetchone()["n"] >= 111
        cur.execute(
            "SELECT count(*) AS n FROM concept_normalization "
            "WHERE field = 'bank_revenue'"
        )
        assert cur.fetchone()["n"] >= 3
        cur.execute(
            "SELECT count(*) AS n FROM concept_normalization "
            "WHERE namespace = '*' AND concept = 'Equity' "
            "AND field = 'stockholders_equity'"
        )
        assert cur.fetchone()["n"] == 1


def test_core_financials_has_the_eight_canonical_fields(db_connection):
    with db_connection.cursor() as cur:
        columns = _columns(cur, "core_financials")

    assert {
        "company_id",
        "fiscal_year",
        "period_end",
        "revenue",
        "net_income",
        "operating_income",
        "gross_profit",
        "total_assets",
        "total_liabilities",
        "stockholders_equity",
        "cash",
    } <= columns


def test_financial_facts_normalized_view_columns(db_connection):
    with db_connection.cursor() as cur:
        columns = _columns(cur, "financial_facts_normalized")

    assert {"namespace", "concept", "field", "normalized_concept"} <= columns


def test_balance_effective_exposes_derived_liabilities(db_connection):
    with db_connection.cursor() as cur:
        columns = _columns(cur, "balance_effective")

    assert {"liabilities_effective", "liabilities_derived"} <= columns


def test_data_quality_issues_table_exists(db_connection):
    with db_connection.cursor() as cur:
        cur.execute("SELECT to_regclass('public.data_quality_issues') AS t")
        assert cur.fetchone()["t"] is not None


def test_migration_is_idempotent():
    """Applying 0022 twice must not fail (IF NOT EXISTS / ON CONFLICT)."""
    sql = MIGRATION.read_text(encoding="utf-8")
    with psycopg.connect(
        _test_dsn(), autocommit=True
    ) as conn, conn.cursor() as cur:
        cur.execute(sql)
        cur.execute(sql)


def test_rollback_drops_the_new_objects(db_connection):
    """DROP order works and the transaction can restore the schema."""
    with db_connection.cursor() as cur:
        cur.execute("DROP VIEW IF EXISTS balance_effective")
        cur.execute("DROP VIEW IF EXISTS financial_facts_normalized")
        cur.execute("DROP MATERIALIZED VIEW IF EXISTS core_financials")
        cur.execute("DROP TABLE IF EXISTS data_quality_issues")
        cur.execute("DROP TABLE IF EXISTS concept_normalization")
        db_connection.rollback()
        cur.execute("SELECT to_regclass('public.concept_normalization') AS t")
        assert cur.fetchone()["t"] is not None
        cur.execute("SELECT to_regclass('public.core_financials') AS t")
        assert cur.fetchone()["t"] is not None


def _test_dsn() -> str:
    import os

    return (
        f"postgresql://{os.environ.get('TEST_DB_USER', 'financial')}:"
        f"{os.environ.get('TEST_DB_PASSWORD', 'test')}@"
        f"{os.environ.get('TEST_DB_HOST', 'localhost')}:"
        f"{os.environ.get('TEST_DB_PORT', '5432')}/"
        f"{os.environ.get('TEST_DB_NAME', 'financial_database_test')}"
    )
