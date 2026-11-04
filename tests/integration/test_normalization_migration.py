"""Migration/contract tests for the v0.2 normalization layer.

These run against the test database after ``financial_database.cli migrate``.
They do not insert production facts: they validate the catalog, the seeded
mapping and the idempotence/rollback of migrations 0022 and 0023. The
large-cap production check is opt-in (``FDB_PROD_DSN``) and skips when the
production database is not reachable.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations"
    / "0022_normalization_v0.2.sql"
)
MIGRATION_0023 = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations"
    / "0023_equity_nci_alias.sql"
)
NCI_CONCEPT = "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"
LARGE_CAPS = ("JNJ", "CAT", "T", "VZ", "CSX", "ADM", "PG")


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
    with psycopg.connect(_test_dsn(), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(sql)
        cur.execute(sql)


def test_nci_migration_is_idempotent():
    """Applying 0023 twice must not fail (ON CONFLICT DO NOTHING)."""
    sql = MIGRATION_0023.read_text(encoding="utf-8")
    with psycopg.connect(_test_dsn(), autocommit=True) as conn, conn.cursor() as cur:
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


def test_nci_equity_alias_rows_are_seeded(db_connection):
    with db_connection.cursor() as cur:
        cur.execute(
            "SELECT namespace, field, normalized_concept "
            "FROM concept_normalization WHERE concept = %s "
            "ORDER BY namespace",
            (NCI_CONCEPT,),
        )
        rows = cur.fetchall()

    assert {row["namespace"] for row in rows} == {"us-gaap", "ifrs-full"}
    for row in rows:
        assert row["field"] == "stockholders_equity"
        assert row["normalized_concept"] == "StockholdersEquity"


def test_nci_equity_alias_feeds_the_normalized_view(db_connection):
    """A us-gaap NCI fact is exposed as stockholders_equity."""
    with db_connection.cursor() as cur:
        cur.execute("SELECT id FROM data_providers WHERE name = 'SEC EDGAR' LIMIT 1")
        provider = cur.fetchone()
        if provider is None:
            pytest.skip("SEC EDGAR provider not seeded in the test database")
        cur.execute(
            "INSERT INTO companies (legal_name) "
            "VALUES ('NCI alias contract test') RETURNING id"
        )
        company_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO financial_facts
              (company_id, provider_id, namespace, concept, value, unit,
               period_end, fiscal_year, fiscal_period, filing_date)
            VALUES (%s, %s, 'us-gaap', %s, 123000000, 'USD',
                    '2099-12-31', 2099, 'FY', '2099-12-31')
            """,
            (company_id, provider["id"], NCI_CONCEPT),
        )
        cur.execute(
            """
            SELECT field, normalized_concept, value
            FROM financial_facts_normalized
            WHERE company_id = %s AND concept = %s
            """,
            (company_id, NCI_CONCEPT),
        )
        row = cur.fetchone()

    assert row is not None
    assert row["field"] == "stockholders_equity"
    assert row["normalized_concept"] == "StockholdersEquity"
    assert row["value"] == 123000000


@pytest.mark.parametrize("ticker", LARGE_CAPS)
def test_large_caps_have_equity_via_nci_alias(ticker):
    """Production regression: the 7 large caps keep non-NULL equity.

    Skipped in CI (no production database). Run locally with
    ``FDB_PROD_DSN`` or the default production DSN.
    """
    dsn = os.environ.get(
        "FDB_PROD_DSN",
        "postgresql://financial:test@localhost:5432/financial_database",
    )
    try:
        conn = psycopg.connect(dsn, row_factory=dict_row)
    except psycopg.OperationalError:
        pytest.skip("production database not reachable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT cl.ticker, cf.fiscal_year, cf.period_end,
                       cf.stockholders_equity
                FROM core_financials cf
                JOIN company_listings cl
                  ON cl.company_id = cf.company_id AND cl.is_active
                WHERE cl.ticker = %s
                ORDER BY cf.fiscal_year DESC, cf.period_end DESC
                LIMIT 1
                """,
                (ticker,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    assert row is not None, f"{ticker} missing from core_financials"
    assert row["stockholders_equity"] is not None, ticker


def _test_dsn() -> str:
    import os

    return (
        f"postgresql://{os.environ.get('TEST_DB_USER', 'financial')}:"
        f"{os.environ.get('TEST_DB_PASSWORD', 'test')}@"
        f"{os.environ.get('TEST_DB_HOST', 'localhost')}:"
        f"{os.environ.get('TEST_DB_PORT', '5432')}/"
        f"{os.environ.get('TEST_DB_NAME', 'financial_database_test')}"
    )
