# ruff: noqa: F601
"""Integration test for financial_facts long string columns (frame, namespace, source_id).

This test verifies that the financial_facts table can store long strings
in frame, namespace, and source_id columns after migration 0020.
"""
import uuid

import pytest

from financial_database.db.repositories.company_repository import CompanyRepository
from financial_database.db.repositories.filing_repository import FilingRepository
from financial_database.db.repositories.financial_fact_repository import (
    FinancialFactRepository,
)


class TestFinancialFactsLongStrings:
    """Test that financial_facts can store long strings in frame, namespace, source_id."""

    @pytest.fixture
    def company(self, db_connection):
        """Create a test company."""
        repo = CompanyRepository(db_connection)
        company = repo.create(legal_name="Test Company for Long Strings")
        return company

    @pytest.fixture
    def provider_id(self, db_connection):
        """Get the SEC provider ID from the database."""
        cur = db_connection.cursor()
        cur.execute("SELECT id FROM data_providers WHERE name = 'SEC EDGAR'")
        row = cur.fetchone()
        if not row:
            raise RuntimeError("SEC EDGAR provider not found in database")
        return row["id"]

    @pytest.fixture
    def filing(self, db_connection, company, provider_id):
        """Create a test filing."""
        repo = FilingRepository(db_connection)
        filing = repo.create(
            company_id=company["id"],
            provider_id=provider_id,
            form="10-K",
            accession_number=f"0000320193-24-{uuid.uuid4().hex[:6].upper()}",
            filing_date="2024-01-15",
            period_start=None,
            period_end="2023-12-31",
            fiscal_year=2023,
            fiscal_period="FY",
        )
        return filing

    def test_long_frame_insert(self, db_connection, company, provider_id, filing):
        """Test inserting a fact with a very long frame (>500 chars)."""
        repo = FinancialFactRepository(db_connection)

        fact = {
            "company_id": company["id"],
            "filing_id": filing["id"],
            "provider_id": provider_id,
            "concept": "TestConcept",
            "namespace": "us-gaap",
            "value": 1000000,
            "unit": "USD",
            "period_start": None,
            "period_end": "2023-12-31",
            "fiscal_year": 2023,
            "fiscal_period": "FY",
            "form": "10-K",
            "source_id": "test_source_1",
            "filing_id": str(filing["id"]),
            "namespace": "us-gaap",
            "frame": "xbrl_metric_" + "x" * 500,
            "filing_date": "2024-01-15",
        }

        repo = FinancialFactRepository(db_connection)
        result = repo.create(**fact)
        assert result is not None
        assert result["frame"] == "xbrl_metric_" + "x" * 500

    def test_long_namespace_insert(self, db_connection, company, provider_id, filing):
        """Test inserting a fact with a very long namespace (>300 chars)."""
        repo = FinancialFactRepository(db_connection)

        long_namespace = "http://xbrl.sec.gov/taxonomy/2024/" + "x" * 300

        fact = {
            "company_id": company["id"],
            "filing_id": filing["id"],
            "provider_id": provider_id,
            "concept": "TestConcept",
            "namespace": long_namespace,
            "value": 1000000,
            "unit": "USD",
            "period_start": None,
            "period_end": "2023-12-31",
            "fiscal_year": 2023,
            "fiscal_period": "FY",
            "form": "10-K",
            "source_id": "test_source_1",
            "filing_id": str(filing["id"]),
            "frame": "test_frame",
            "filing_date": "2024-01-15",
        }

        repo = FinancialFactRepository(db_connection)
        result = repo.create(**fact)
        assert result is not None
        assert result["namespace"] == long_namespace

    def test_long_source_id_insert(self, db_connection, company, provider_id, filing):
        """Test inserting a fact with a very long source_id (>500 chars)."""
        repo = FinancialFactRepository(db_connection)

        fact = {
            "company_id": company["id"],
            "filing_id": filing["id"],
            "provider_id": provider_id,
            "concept": "TestConcept",
            "namespace": "us-gaap",
            "value": 1000000,
            "unit": "USD",
            "period_start": None,
            "period_end": "2023-12-31",
            "fiscal_year": 2023,
            "fiscal_period": "FY",
            "form": "10-K",
            "source_id": "accession_" + "x" * 500,
            "filing_id": str(filing["id"]),
            "namespace": "us-gaap",
            "frame": "test_frame",
            "filing_date": "2024-01-15",
        }

        repo = FinancialFactRepository(db_connection)
        result = repo.create(**fact)
        assert result is not None
        assert result["source_id"] == "accession_" + "x" * 500

    def test_all_long_strings_together(self, db_connection, company, provider_id, filing):
        """Test inserting a fact with all three long string fields simultaneously."""
        repo = FinancialFactRepository(db_connection)

        fact = {
            "company_id": company["id"],
            "filing_id": filing["id"],
            "provider_id": provider_id,
            "concept": "AllLongStringsTest",
            "namespace": "http://xbrl.sec.gov/taxonomy/2024/" + "x" * 300,
            "value": 1000000,
            "unit": "USD",
            "period_start": None,
            "period_end": "2023-12-31",
            "fiscal_year": 2023,
            "fiscal_period": "FY",
            "form": "10-K",
            "source_id": "accession_" + "x" * 500,
            "filing_date": "2024-01-15",
            "filing_id": str(filing["id"]),
            "frame": "xbrl_metric_" + "x" * 500,
        }

        repo = FinancialFactRepository(db_connection)
        result = repo.create(**fact)
        assert result is not None
        assert result["namespace"] == "http://xbrl.sec.gov/taxonomy/2024/" + "x" * 300
        assert result["frame"] == "xbrl_metric_" + "x" * 500
        assert result["source_id"] == "accession_" + "x" * 500