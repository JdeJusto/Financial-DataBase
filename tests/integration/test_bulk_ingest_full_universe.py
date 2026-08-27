"""Regression tests for SECBulkIngester.ingest_full_universe.

Covers the bug where a stale checkpoint caused zero companies to be processed,
and the ``force`` flag that resets progress.
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


class TestIngestFullUniverse:
    """Regression tests for ingest_full_universe company processing."""

    @pytest.mark.asyncio
    async def test_processes_all_companies_on_fresh_run(self, tmp_path):
        """A fresh run (no checkpoint) should process every company."""
        ingester, client = _make_ingester(tmp_path)
        _configure_client(client, _five_companies())

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
            stats = await ingester.ingest_full_universe()

        assert stats.companies_processed == 5
        assert mock_ticker.call_count == 5

    @pytest.mark.asyncio
    async def test_second_run_does_not_reprocess(self, tmp_path):
        """A resume run should skip already-processed companies (no duplicates)."""
        ingester, client = _make_ingester(tmp_path)
        _configure_client(client, _five_companies())

        with (
            patch.object(ingester, "_get_provider_id", return_value=_PROVIDER_ID),
            patch.object(
                ingester, "_process_ticker_item", new_callable=AsyncMock
            ) as first_ticker,
            patch.object(
                ingester, "_process_company_facts", new_callable=AsyncMock
            ),
            patch.object(
                ingester, "_process_submissions_from_api", new_callable=AsyncMock
            ),
        ):
            first_stats = await ingester.ingest_full_universe()

        assert first_stats.companies_processed == 5
        assert first_ticker.call_count == 5

        # Second run: checkpoint is persisted, so all companies are skipped.
        with (
            patch.object(ingester, "_get_provider_id", return_value=_PROVIDER_ID),
            patch.object(
                ingester, "_process_ticker_item", new_callable=AsyncMock
            ) as second_ticker,
            patch.object(
                ingester, "_process_company_facts", new_callable=AsyncMock
            ),
            patch.object(
                ingester, "_process_submissions_from_api", new_callable=AsyncMock
            ),
        ):
            second_stats = await ingester.ingest_full_universe()

        assert second_stats.companies_processed == 0
        assert second_ticker.call_count == 0

    @pytest.mark.asyncio
    async def test_force_ignores_stale_checkpoint(self, tmp_path):
        """--force must ignore a stale checkpoint and reprocess all companies."""
        ingester, client = _make_ingester(tmp_path)
        _configure_client(client, _five_companies())

        # Simulate a stale checkpoint whose last_processed_cik is beyond every
        # company in the current universe (the reported 0-companies bug).
        stale = BulkImportCheckpoint(
            dataset="full_universe",
            provider="SEC EDGAR",
            source_file="api://data.sec.gov",
            last_processed_cik="9999999999",
            companies_processed=608,
            facts_processed=1000,
            filings_processed=500,
        )
        ingester._save_checkpoint(stale)

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
            stats = await ingester.ingest_full_universe(force=True)

        assert stats.companies_processed == 5
        assert mock_ticker.call_count == 5

        # The reset checkpoint should no longer skip companies.
        saved = ingester._load_checkpoint("full_universe")
        assert saved is not None
        assert saved.last_processed_cik == "0001652044"

    @pytest.mark.asyncio
    async def test_force_flag_resets_previous_progress(self, tmp_path):
        """force=True resets counts even when a partial checkpoint exists."""
        ingester, client = _make_ingester(tmp_path)
        _configure_client(client, _five_companies())

        partial = BulkImportCheckpoint(
            dataset="full_universe",
            provider="SEC EDGAR",
            last_processed_cik="0000320193",
            companies_processed=1,
            facts_processed=10,
            filings_processed=2,
        )
        ingester._save_checkpoint(partial)

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
            stats = await ingester.ingest_full_universe(force=True)

        assert stats.companies_processed == 5
        assert mock_ticker.call_count == 5

    @pytest.mark.asyncio
    async def test_stale_checkpoint_from_other_source_is_ignored(self, tmp_path):
        """A checkpoint saved against a different tickers source is not reused."""
        ingester, client = _make_ingester(tmp_path)
        _configure_client(client, _five_companies())

        stale = BulkImportCheckpoint(
            dataset="full_universe",
            provider="SEC EDGAR",
            source_file="other://source",
            last_processed_cik="9999999999",
            companies_processed=608,
            facts_processed=1000,
            filings_processed=500,
        )
        ingester._save_checkpoint(stale)

        with (
            patch(
                "financial_database.providers.sec.bulk_ingest.SEC_COMPANY_TICKERS_URL",
                "test://source",
            ),
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
            stats = await ingester.ingest_full_universe()

        # Without --force, the mismatched-source checkpoint is ignored.
        assert stats.companies_processed == 5
        assert mock_ticker.call_count == 5
