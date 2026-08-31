"""Regression tests for SECBulkIngester.ingest_full_universe.

Covers the bug where a stale checkpoint caused zero companies to be processed,
and the ``force`` flag that resets progress.
"""

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from financial_database.providers.sec.bulk_ingest import (
    BulkImportCheckpoint,
    BulkImportStats,
    SECBulkIngestAbort,
    SECBulkIngester,
)
from financial_database.providers.sec.client import (
    SECNotFoundError,
    SECServerError,
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

    @pytest.mark.asyncio
    async def test_commit_happens_before_checkpoint_save(self, tmp_path):
        """conn.commit() must run before _save_checkpoint() for each company.

        Reversing this order marks a company as processed before its data is
        durable, so a crash in between loses data on resume.
        """
        ingester, client = _make_ingester(tmp_path)
        _configure_client(client, _five_companies())

        events = []

        with (
            patch.object(ingester, "_get_provider_id", return_value=_PROVIDER_ID),
            patch.object(ingester, "_process_ticker_item", new_callable=AsyncMock),
            patch.object(ingester, "_process_company_facts", new_callable=AsyncMock),
            patch.object(
                ingester, "_process_submissions_from_api", new_callable=AsyncMock
            ),
            patch.object(
                ingester.conn, "commit", side_effect=lambda: events.append("commit")
            ),
            patch.object(
                ingester,
                "_save_checkpoint",
                side_effect=lambda cp: events.append("save"),
            ),
        ):
            await ingester.ingest_full_universe()

        # Strip the initial "fresh start" save. The next 10 events must be the
        # 5 per-company commit -> save pairs (never save -> commit). Later
        # events come from the final checkpoint save and the import-run finish.
        core = list(events)
        if core and core[0] == "save":
            core = core[1:]

        assert len(core) >= 10
        assert core[0:10:2] == ["commit"] * 5
        assert core[1:10:2] == ["save"] * 5

    @pytest.mark.asyncio
    async def test_filing_id_map_passed_to_process_company_facts(self, tmp_path):
        """The accession->filing_id map must reach _process_company_facts."""
        ingester, client = _make_ingester(tmp_path)
        _configure_client(client, _five_companies())

        filing_map = {"000032019323000106": "filing-uuid-1"}

        with (
            patch.object(ingester, "_get_provider_id", return_value=_PROVIDER_ID),
            patch.object(ingester, "_process_ticker_item", new_callable=AsyncMock),
            patch.object(ingester, "_get_company_id_by_cik", return_value="company-uuid-1"),
            patch.object(ingester, "_build_filing_id_map", return_value=filing_map),
            patch.object(
                ingester, "_process_submissions_from_api", new_callable=AsyncMock
            ),
            patch.object(
                ingester, "_process_company_facts", new_callable=AsyncMock
            ) as mock_facts,
        ):
            await ingester.ingest_full_universe()

        assert mock_facts.call_count == 5
        for call in mock_facts.call_args_list:
            assert call.args[2] == filing_map

    @pytest.mark.asyncio
    async def test_companyfacts_404_is_skipped_without_crashing(self, tmp_path):
        """A 404 on companyfacts is recorded and the loop continues."""
        ingester, client = _make_ingester(tmp_path)
        _configure_client(client, _five_companies())
        client.get_company_facts = AsyncMock(
            side_effect=SECNotFoundError("Resource not found")
        )

        with (
            patch.object(ingester, "_get_provider_id", return_value=_PROVIDER_ID),
            patch.object(ingester, "_process_ticker_item", new_callable=AsyncMock),
            patch.object(
                ingester, "_process_submissions_from_api", new_callable=AsyncMock
            ),
            patch.object(
                ingester, "_process_company_facts", new_callable=AsyncMock
            ) as mock_facts,
        ):
            stats = await ingester.ingest_full_universe()

        assert stats.companies_processed == 5
        assert mock_facts.call_count == 0
        assert len(stats.errors) == 5
        assert all(e.get("expected_404") for e in stats.errors)

    @pytest.mark.asyncio
    async def test_import_run_and_raw_documents_recorded(self, tmp_path):
        """The bulk path must write an import_run and raw_document records."""
        ingester, client = _make_ingester(tmp_path)
        _configure_client(client, _five_companies())

        ingester.import_runs = MagicMock()
        ingester.import_runs.create = MagicMock(return_value={"id": "run-uuid-1"})
        ingester.import_runs.update = MagicMock()

        with (
            patch.object(ingester, "_get_provider_id", return_value=_PROVIDER_ID),
            patch.object(ingester, "_process_ticker_item", new_callable=AsyncMock),
            patch.object(
                ingester, "_process_submissions_from_api", new_callable=AsyncMock
            ),
            patch.object(
                ingester, "_process_company_facts", new_callable=AsyncMock
            ),
            patch.object(ingester, "_record_raw_document") as mock_record,
        ):
            await ingester.ingest_full_universe()

        ingester.import_runs.create.assert_called_once()
        success_calls = [
            c
            for c in ingester.import_runs.update.call_args_list
            if c.kwargs.get("status") == "success"
        ]
        assert len(success_calls) == 1
        # 2 raw docs (submissions + companyfacts) per company × 5 companies.
        assert mock_record.call_count == 10

    @pytest.mark.asyncio
    async def test_transient_error_aborts_without_advancing_checkpoint(self, tmp_path):
        """A 429/5xx aborts the run and does not mark the company processed."""
        ingester, client = _make_ingester(tmp_path)
        _configure_client(client, _five_companies())
        client.get_company_facts = AsyncMock(
            side_effect=SECServerError("Server error 500")
        )

        with (
            patch.object(ingester, "_get_provider_id", return_value=_PROVIDER_ID),
            patch.object(ingester, "_process_ticker_item", new_callable=AsyncMock),
            patch.object(
                ingester, "_process_submissions_from_api", new_callable=AsyncMock
            ),
            patch.object(
                ingester, "_process_company_facts", new_callable=AsyncMock
            ),
            pytest.raises(SECBulkIngestAbort, match="Transient SEC error"),
        ):
            await ingester.ingest_full_universe()

        # The checkpoint must NOT have advanced past the failed company, so it
        # is retried on resume instead of being silently skipped.
        saved = ingester._load_checkpoint("full_universe")
        assert saved is not None
        assert saved.last_processed_cik is None

    def test_parse_company_facts_dict_preserves_units(self, tmp_path):
        """The bulk parse path must preserve per-value units (USD, shares)."""
        ingester, _ = _make_ingester(tmp_path)
        facts_dict = {
            "us-gaap": {
                "Assets": {
                    "label": "Assets",
                    "unit": "",
                    "units": {
                        "USD": [
                            {
                                "val": 1000,
                                "start": None,
                                "end": "2023-09-30",
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2023-11-03",
                                "accn": "0000320193-23-000106",
                                "frame": None,
                            }
                        ],
                        "shares": [
                            {
                                "val": 15500000,
                                "start": None,
                                "end": "2023-09-30",
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2023-11-03",
                                "accn": "0000320193-23-000106",
                                "frame": None,
                            }
                        ],
                    },
                },
            },
        }

        result = ingester._parse_company_facts_dict(facts_dict)
        values = result["us-gaap"]["Assets"].values
        assert {v.unit for v in values} == {"USD", "shares"}

    @pytest.mark.asyncio
    async def test_process_company_facts_commits_before_batches(self, tmp_path):
        """Each 500-fact batch must be a real commit, not a nested savepoint.

        _process_company_facts must commit the pending outer transaction first,
        so each conn.transaction() is a durable commit.
        """
        ingester, _ = _make_ingester(tmp_path)

        facts = []
        for _ in range(1200):  # 3 batches of 500
            f = MagicMock()
            f.concept = "Concept"
            f.namespace = "us-gaap"
            f.value = 1.0
            f.unit = "USD"
            f.period_start = None
            f.period_end = None
            f.fiscal_year = 2023
            f.fiscal_period = "FY"
            f.provider_id = _PROVIDER_ID
            f.source_id = "src"
            f.filing_id = None
            f.form = "10-K"
            f.filing_date = None
            f.frame = None
            facts.append(f)

        ingester.parser = MagicMock()
        ingester.parser.parse_company_facts = MagicMock(return_value=facts)
        ingester.facts = MagicMock()
        ingester.facts.create_batch = MagicMock(return_value=[])

        events = []
        ingester.conn.commit = MagicMock(
            side_effect=lambda: events.append("commit")
        )
        ingester.conn.transaction = MagicMock(
            side_effect=lambda: (
                events.append("transaction") or contextlib.nullcontext()
            )
        )

        await ingester._process_company_facts(
            "0000320193",
            {"facts": {}, "entity_name": "Apple Inc."},
            {},
            _PROVIDER_ID,
            BulkImportStats(),
        )

        # Commit the outer transaction first, then one transaction per batch.
        assert events[0] == "commit"
        assert events.count("transaction") == 3
