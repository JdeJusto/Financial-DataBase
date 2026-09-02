"""
This test demonstrates the fix for the stale checkpoint issue and can be added to
tests/integration/test_bulk_ingest_resume.py or tests/integration/test_bulk_ingest_full_universe.py
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from financial_database.providers.sec.bulk_ingest import (
    BulkImportCheckpoint,
    SECBulkIngester,
)
from financial_database.providers.sec.models import (
    SECCompany,
    SECCompanyFacts,
    SECSubmissions,
)


def _make_company(cik: str, name: str, ticker: str) -> SECCompany:
    return SECCompany(cik=cik, name=name, ticker=ticker, exchange="NASDAQ")


def _make_ingester(tmp_path):
    conn = MagicMock()
    client = MagicMock()
    client._raw_dir = str(tmp_path)
    parser = MagicMock()

    ingester = SECBulkIngester(
        conn=conn,
        client=client,
        parser=parser,
        raw_dir=tmp_path,
        checkpoint_dir=tmp_path / "checkpoints",
    )
    return ingester, client


def _configure_client(client, companies):
    client.get_company_tickers = AsyncMock(return_value=companies)
    client.get_company_facts = AsyncMock(
        return_value=SECCompanyFacts(cik="0000320193", entity_name="Apple Inc.", facts={})
    )
    client.get_submissions = AsyncMock(
        return_value=SECSubmissions(cik="0000320193", entity_name="Apple Inc.", filings=[])
    )


def _five_companies():
    return [
        _make_company("0000320193", "Apple Inc.", "AAPL"),
        _make_company("0000789019", "Microsoft Corp", "MSFT"),
        _make_company("0001018724", "Amazon Com Inc", "AMZN"),
        _make_company("0001318605", "Tesla Inc", "TSLA"),
        _make_company("0001652044", "Alphabet Inc", "GOOGL"),
    ]


_PROVIDER_ID = "12345678-1234-5678-1234-567812345678"


@pytest.mark.asyncio
async def test_stale_checkpoint_higher_than_all_ciks_processes_all(tmp_path):
    """
    Test for the bug fix: when checkpoint's last_processed_cik is higher than
    any CIK in the current company universe, we should process all companies
    (not skip all due to cik <= checkpoint.last_processed_cik).

    This addresses the issue where a stale checkpoint from a previous run with
    a different universe would cause zero companies to be processed in the current run.
    """
    ingester, client = _make_ingester(tmp_path)
    companies = _five_companies()
    _configure_client(client, companies)

    # Create a stale checkpoint where last_processed_cik is higher than any CIK in current universe
    # This simulates the scenario where we had a previous run with a different/universe
    # and now we're running with a subset or different set of companies
    stale_checkpoint = BulkImportCheckpoint(
        dataset="full_universe",
        provider="SEC EDGAR",
        source_file="https://www.sec.gov/files/company_tickers.json",  # Same source
        last_processed_cik="9999999999",  # Higher than any CIK in our current list
        companies_processed=0,  # Important: no companies actually processed in THIS universe
        facts_processed=0,
        filings_processed=0,
    )
    ingester._save_checkpoint(stale_checkpoint)

    # Mock the methods to track calls
    with (
        patch.object(ingester, "_get_provider_id", return_value=_PROVIDER_ID),
        patch.object(
            ingester, "_process_ticker_item", new_callable=AsyncMock
        ) as mock_ticker,
        patch.object(
            ingester, "_process_company_facts", new_callable=AsyncMock
        ),
        patch.object(
            ingester, "_process_submissions_from_api", new_callable=AsyncMock
        ),
    ):
        # This should process ALL companies, not skip all
        stats = await ingester.ingest_full_universe()

        # Verify all companies were processed
        assert stats.companies_processed == 5
        assert mock_ticker.call_count == 5

        # Verify the checkpoint was updated correctly
        saved_checkpoint = ingester._load_checkpoint("full_universe")
        assert saved_checkpoint is not None
        assert saved_checkpoint.last_processed_cik == "0001652044"  # Last CIK processed
        assert saved_checkpoint.companies_processed == 5