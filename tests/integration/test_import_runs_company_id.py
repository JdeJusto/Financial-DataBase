"""Integration test for import_runs.company_id (migration 0021).

Verifies that per-company import runs (sec sync / submissions / companyfacts)
record the company they ingested, that batch pipelines stay unscoped, and
that deleting a company keeps the run with a NULL company_id (ON DELETE SET
NULL) instead of deleting provenance.
"""

import uuid

import pytest

from financial_database.db.repositories.company_repository import CompanyRepository
from financial_database.db.repositories.import_run_repository import (
    ImportRunRepository,
)


class TestImportRunsCompanyId:
    @pytest.fixture
    def company(self, db_connection):
        return CompanyRepository(db_connection).create(
            legal_name=f"ImportRunScope {uuid.uuid4().hex[:10]}"
        )

    @pytest.fixture
    def provider_id(self, db_connection):
        with db_connection.cursor() as cur:
            cur.execute("SELECT id FROM data_providers WHERE name = 'SEC EDGAR'")
            row = cur.fetchone()
        if not row:
            pytest.skip("SEC EDGAR provider not seeded in the test database")
        return str(row["id"])

    def test_company_scoped_run_persists_and_is_queryable(
        self, db_connection, company, provider_id
    ):
        runs = ImportRunRepository(db_connection)
        company_id = str(company["id"])

        run = runs.create(provider_id, "sec_sync", "success", company_id=company_id)
        db_connection.commit()

        assert str(run["company_id"]) == company_id
        latest = runs.get_latest_for_company(company_id)
        assert latest is not None
        assert str(latest["id"]) == str(run["id"])
        assert latest["pipeline"] == "sec_sync"
        assert latest["status"] == "success"
        assert str(latest["company_id"]) == company_id

    def test_batch_run_stays_unscoped(self, db_connection, provider_id):
        runs = ImportRunRepository(db_connection)

        run = runs.create(provider_id, "sec_update_incremental", "running")
        db_connection.commit()

        assert run["company_id"] is None

    def test_company_delete_keeps_run_with_null_company(
        self, db_connection, company, provider_id
    ):
        runs = ImportRunRepository(db_connection)
        companies = CompanyRepository(db_connection)
        company_id = str(company["id"])
        run = runs.create(provider_id, "sec_sync", "success", company_id=company_id)
        db_connection.commit()

        companies_conn = db_connection
        with companies_conn.cursor() as cur:
            cur.execute("DELETE FROM companies WHERE id = %s", (company_id,))
        db_connection.commit()

        with db_connection.cursor() as cur:
            cur.execute(
                "SELECT company_id FROM import_runs WHERE id = %s", (str(run["id"]),)
            )
            still_there = cur.fetchone()
        assert still_there is not None  # provenance kept
        assert still_there["company_id"] is None  # scoped field cleared
        assert runs.get_latest_for_company(company_id) is None
