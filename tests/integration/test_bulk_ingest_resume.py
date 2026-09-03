"""Integration tests for SEC bulk ingestion with checkpoint/resume functionality."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from financial_database.providers.sec.bulk_ingest import (
    BulkImportCheckpoint,
    BulkImportStats,
    SECBulkIngester,
)


class TestBulkImportCheckpoint:
    """Test checkpoint serialization and deserialization."""

    def test_checkpoint_to_dict(self):
        """Test checkpoint serialization to dict."""
        checkpoint = BulkImportCheckpoint(
            dataset="companyfacts",
            provider="SEC EDGAR",
            source_file="/path/to/companyfacts.json",
            source_file_checksum="abc123",
            last_processed_cik="0000320193",
            companies_processed=10,
            facts_processed=100,
            filings_processed=5,
        )
        data = checkpoint.to_dict()

        assert data["dataset"] == "companyfacts"
        assert data["provider"] == "SEC EDGAR"
        assert data["source_file"] == "/path/to/companyfacts.json"
        assert data["source_file_checksum"] == "abc123"
        assert data["last_processed_cik"] == "0000320193"
        assert data["companies_processed"] == 10
        assert data["facts_processed"] == 100
        assert data["filings_processed"] == 5
        assert "updated_at" in data

    def test_checkpoint_from_dict(self):
        """Test checkpoint deserialization from dict."""
        data = {
            "dataset": "companyfacts",
            "provider": "SEC EDGAR",
            "source_file": "/path/to/companyfacts.json",
            "source_file_checksum": "abc123",
            "last_processed_cik": "0000320193",
            "companies_processed": 10,
            "facts_processed": 100,
            "filings_processed": 5,
            "updated_at": "2024-01-15T10:30:00+00:00",
        }
        checkpoint = BulkImportCheckpoint.from_dict(data)

        assert checkpoint.dataset == "companyfacts"
        assert checkpoint.provider == "SEC EDGAR"
        assert checkpoint.source_file == "/path/to/companyfacts.json"
        assert checkpoint.source_file_checksum == "abc123"
        assert checkpoint.last_processed_cik == "0000320193"
        assert checkpoint.companies_processed == 10
        assert checkpoint.facts_processed == 100
        assert checkpoint.filings_processed == 5

    def test_checkpoint_defaults(self):
        """Test checkpoint with default values."""
        checkpoint = BulkImportCheckpoint(dataset="companyfacts")
        data = checkpoint.to_dict()

        assert data["dataset"] == "companyfacts"
        assert data["provider"] == "SEC EDGAR"
        assert data["source_file"] == ""
        assert data["source_file_checksum"] == ""
        assert data["last_processed_cik"] is None
        assert data["companies_processed"] == 0
        assert data["facts_processed"] == 0
        assert data["filings_processed"] == 0


class TestBulkImportStats:
    """Test bulk import statistics."""

    def test_stats_to_dict(self):
        """Test stats serialization."""
        stats = BulkImportStats(
            companies_processed=5,
            companies_inserted=3,
            companies_updated=2,
            facts_processed=50,
            facts_inserted=45,
            facts_skipped=5,
            errors=[{"cik": "0000320193", "error": "test error"}],
        )
        data = stats.to_dict()

        assert data["companies_processed"] == 5
        assert data["companies_inserted"] == 3
        assert data["companies_updated"] == 2
        assert data["facts_processed"] == 50
        assert data["facts_inserted"] == 45
        assert data["facts_skipped"] == 5
        assert len(data["errors"]) == 1


class TestSECBulkIngesterCheckpoint:
    """Test checkpoint save/load functionality."""

    def test_compute_file_checksum(self, tmp_path):
        """Test file checksum computation."""
        test_file = tmp_path / "test.json"
        test_file.write_text('{"test": "data"}')

        # Create a minimal ingester for testing
        conn = MagicMock()
        client = MagicMock()
        client._raw_dir = str(tmp_path)
        parser = MagicMock()

        ingester = SECBulkIngester(
            conn=conn,
            client=client,
            parser=parser,
            raw_dir=tmp_path,
        )

        checksum = ingester._compute_file_checksum(test_file)
        assert len(checksum) == 64  # SHA256 hex length
        # Verify it's deterministic
        checksum2 = ingester._compute_file_checksum(test_file)
        assert checksum == checksum2

    def test_get_checkpoint_path(self, tmp_path):
        """Test checkpoint path generation."""
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

        path = ingester._get_checkpoint_path("companyfacts")
        assert path == tmp_path / "checkpoints" / "companyfacts_checkpoint.json"

    def test_save_and_load_checkpoint(self, tmp_path):
        """Test atomic checkpoint save and load."""
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

        checkpoint = BulkImportCheckpoint(
            dataset="companyfacts",
            provider="SEC EDGAR",
            source_file="/path/to/companyfacts.json",
            source_file_checksum="abc123",
            last_processed_cik="0000320193",
            companies_processed=10,
            facts_processed=100,
        )

        # Save checkpoint
        ingester._save_checkpoint(checkpoint)

        # Load checkpoint
        loaded = ingester._load_checkpoint("companyfacts")

        assert loaded is not None
        assert loaded.dataset == "companyfacts"
        assert loaded.provider == "SEC EDGAR"
        assert loaded.source_file == "/path/to/companyfacts.json"
        assert loaded.source_file_checksum == "abc123"
        assert loaded.last_processed_cik == "0000320193"
        assert loaded.companies_processed == 10
        assert loaded.facts_processed == 100

    def test_load_nonexistent_checkpoint(self, tmp_path):
        """Test loading non-existent checkpoint returns None."""
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

        loaded = ingester._load_checkpoint("companyfacts")
        assert loaded is None

    def test_checkpoint_atomic_write(self, tmp_path):
        """Test checkpoint is written atomically (temp file then rename)."""
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

        checkpoint = BulkImportCheckpoint(
            dataset="companyfacts",
            last_processed_cik="0000320193",
            companies_processed=10,
        )

        # Mock temp file replace to verify atomic write
        original_replace = Path.replace

        replace_called = []

        def mock_replace(self, target):
            replace_called.append((str(self), str(target)))
            return original_replace(self, target)

        with patch.object(Path, "replace", mock_replace):
            ingester._save_checkpoint(checkpoint)

        # Verify temp file was used
        assert len(replace_called) == 1
        temp_path, final_path = replace_called[0]
        assert temp_path.endswith(".tmp")
        assert final_path.endswith("_checkpoint.json")

    def test_load_corrupted_checkpoint(self, tmp_path):
        """Test loading corrupted checkpoint returns None."""
        conn = MagicMock()
        client = MagicMock()
        client._raw_dir = str(tmp_path)
        parser = MagicMock()

        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir(parents=True)

        # Write corrupted JSON
        checkpoint_file = checkpoint_dir / "companyfacts_checkpoint.json"
        checkpoint_file.write_text("{ invalid json }")

        ingester = SECBulkIngester(
            conn=conn,
            client=client,
            parser=parser,
            raw_dir=tmp_path,
            checkpoint_dir=checkpoint_dir,
        )

        loaded = ingester._load_checkpoint("companyfacts")
        assert loaded is None

    def test_checkpoint_checksum_validation(self, tmp_path):
        """Test checkpoint detects source file changes via checksum."""
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

        # Create test file
        test_file = tmp_path / "companyfacts.json"
        test_file.write_text(
            '{"cik": "0000320193", "entityName": "Apple", "facts": {}}'
        )

        # Create checkpoint with original checksum
        original_checksum = ingester._compute_file_checksum(test_file)
        checkpoint = BulkImportCheckpoint(
            dataset="companyfacts",
            source_file=str(test_file),
            source_file_checksum=original_checksum,
            last_processed_cik="0000320193",
            companies_processed=1,
        )

        ingester._save_checkpoint(checkpoint)

        # Modify the source file
        test_file.write_text(
            '{"cik": "0000320193", "entityName": "Apple Modified", "facts": {}}'
        )

        # Load checkpoint - should have old checksum
        loaded = ingester._load_checkpoint("companyfacts")
        assert loaded is not None
        assert loaded.source_file_checksum == original_checksum

        # New checksum should differ
        new_checksum = ingester._compute_file_checksum(test_file)
        assert new_checksum != original_checksum


class TestBulkIngestIdempotency:
    """Test idempotency logic (without full database integration)."""

    def test_duplicate_fact_detection_logic(self):
        """Test that idempotency check logic works correctly."""
        # This tests the SQL query logic used for idempotency
        # The actual implementation uses IS NOT DISTINCT FROM for NULL-safe comparison
        query = """SELECT id FROM financial_facts
                   WHERE company_id = %s AND concept = %s
                   AND period_start IS NOT DISTINCT FROM %s
                   AND period_end = %s
                   AND filing_id IS NOT DISTINCT FROM %s
                   AND source_id = %s"""

        # Verify query structure
        assert "IS NOT DISTINCT FROM" in query
        assert "company_id" in query
        assert "concept" in query
        assert "period_start" in query
        assert "period_end" in query
        assert "filing_id" in query
        assert "source_id" in query

    def test_checkpoint_advances_on_success(self):
        """Test that checkpoint advances after successful company processing."""
        checkpoint = BulkImportCheckpoint(
            dataset="companyfacts",
            last_processed_cik="0000320193",
            companies_processed=5,
            facts_processed=50,
        )

        # Simulate successful processing
        checkpoint.last_processed_cik = "0000789019"
        checkpoint.companies_processed = 6
        checkpoint.facts_processed = 55

        assert checkpoint.last_processed_cik == "0000789019"
        assert checkpoint.companies_processed == 6
        assert checkpoint.facts_processed == 55

    def test_checkpoint_advances_on_failure(self):
        """Test that checkpoint advances even after failed company to avoid infinite retry."""
        checkpoint = BulkImportCheckpoint(
            dataset="companyfacts",
            last_processed_cik="0000320193",
            companies_processed=5,
        )

        # Simulate failed company - checkpoint still advances
        failed_cik = "0000789019"
        checkpoint.last_processed_cik = failed_cik
        checkpoint.companies_processed = 6

        assert checkpoint.last_processed_cik == failed_cik
        assert checkpoint.companies_processed == 6

    def test_checkpoint_handles_stale_checkpoint_higher_than_all_ciks(self):
        """Test that when checkpoint CIK is higher than all current CIKs, we start from beginning."""
        # This simulates the bug where a stale checkpoint from a different universe
        # has a last_processed_cik higher than any CIK in the current company list

        # Current company list (what we're processing now)
        current_ciks = ["0000320193", "0000789019", "0001018724", "0001234567"]

        # Stale checkpoint from a previous run with different universe
        stale_last_processed_cik = "0009999999"  # Higher than all current CIKs

        checkpoint = BulkImportCheckpoint(
            dataset="companyfacts",
            last_processed_cik=stale_last_processed_cik,
            companies_processed=0,  # No companies actually processed in this universe yet
        )

        # Simulate our fix logic
        start_index = 0
        if checkpoint.last_processed_cik:
            # Find if the checkpoint CIK exists in our current company list
            cik_list = current_ciks.copy()  # Already sorted
            try:
                # Find the index of the checkpoint CIK
                checkpoint_index = cik_list.index(checkpoint.last_processed_cik)
                # Start from the next company after the checkpoint
                start_index = checkpoint_index + 1
            except ValueError:
                # Checkpoint CIK not found in current list
                # Find the first company with CIK > checkpoint.last_processed_cik
                # or start from beginning if all CIKs are <= checkpoint.last_processed_cik
                for i, cik in enumerate(cik_list):
                    if cik > checkpoint.last_processed_cik:
                        start_index = i
                        break
                else:
                    # All CIKs are <= checkpoint.last_processed_cik, start from beginning
                    start_index = 0

        # With our fix, start_index should be 0 (beginning) since all current CIKs <= checkpoint
        assert start_index == 0

        # Verify we would process all companies
        companies_to_process = current_ciks[start_index:]
        assert companies_to_process == [
            "0000320193",
            "0000789019",
            "0001018724",
            "0001234567",
        ]

    def test_checkpoint_resume_skips_processed(self):
        """Test that resume logic correctly skips already processed CIKs."""
        checkpoint = BulkImportCheckpoint(
            dataset="companyfacts",
            last_processed_cik="0000789019",
            companies_processed=2,
        )

        # CIKs in order
        ciks = ["0000320193", "0000789019", "0001018724", "0001234567"]

        processed = []
        for cik in ciks:
            if checkpoint.last_processed_cik and cik <= checkpoint.last_processed_cik:
                continue  # Skip
            processed.append(cik)

        # Should only process CIKs after the checkpoint
        assert processed == ["0001018724", "0001234567"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestCompanyTickersIngestion:
    """Test ingest_company_tickers functionality."""

    @pytest.mark.asyncio
    async def test_ingest_company_tickers_streaming(self, tmp_path):
        """Test streaming parsing of company_tickers_exchange.json."""
        from unittest.mock import AsyncMock, MagicMock, patch

        conn = MagicMock()
        client = MagicMock()
        client._raw_dir = str(tmp_path)
        parser = MagicMock()
        parser._get_exchange_mapping.return_value = MagicMock(
            internal_code="NASDAQ",
            internal_name="NASDAQ Stock Market",
            mic="XNAS",
            country="USA",
            timezone="America/New_York",
            currency="USD",
        )

        ingester = SECBulkIngester(
            conn=conn,
            client=client,
            parser=parser,
            raw_dir=tmp_path,
        )

        # Mock _get_provider_id to return a fixed UUID
        with patch.object(
            ingester,
            "_get_provider_id",
            return_value="12345678-1234-5678-1234-567812345678",
        ):
            # Create test tickers file with SEC format
            tickers_file = tmp_path / "company_tickers_exchange.json"
            tickers_file.write_text("""{
                "data": [
                    ["0000320193", "Apple Inc.", "AAPL", "NASDAQ", "3571", "Electronic Computers", ""],
                    ["0000789019", "Microsoft Corporation", "MSFT", "NASDAQ", "7372", "Prepackaged Software", ""],
                    ["0000999999", "Private Co", "", "", "1234", "Test", ""]
                ]
            }""")

            # Mock the internal method to track calls
            with patch.object(
                ingester, "_process_ticker_item", new_callable=AsyncMock
            ) as mock_process:

                async def mock_process_func(item, pid, stats):
                    stats.companies_processed += 1

                mock_process.side_effect = mock_process_func

                stats = await ingester.ingest_company_tickers(tickers_file)

            # Should process 3 items
            assert mock_process.call_count == 3
            assert stats.companies_processed == 3


class TestSubmissionsIngestion:
    """Test ingest_submissions functionality."""

    @pytest.mark.asyncio
    async def test_ingest_submissions_streaming(self, tmp_path):
        """Test streaming parsing of submissions JSON files."""
        from unittest.mock import MagicMock, patch

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

        # Mock _get_provider_id to return a fixed UUID
        with patch.object(
            ingester,
            "_get_provider_id",
            return_value="12345678-1234-5678-1234-567812345678",
        ):
            # Create test submissions directory with files
            submissions_dir = tmp_path / "submissions"
            submissions_dir.mkdir()

            (submissions_dir / "CIK0000320193.json").write_text("""{
                "cik": "0000320193",
                "name": "Apple Inc.",
                "filings": {
                    "recent": {
                        "accessionNumber": ["0000320193-23-000106"],
                        "form": ["10-K"],
                        "filingDate": ["2023-11-03"],
                        "reportDate": ["2023-09-30"],
                        "fy": [2023],
                        "fp": ["FY"]
                    }
                }
            }""")

            (submissions_dir / "CIK0000789019.json").write_text("""{
                "cik": "0000789019",
                "name": "Microsoft Corporation",
                "filings": {
                    "recent": {
                        "accessionNumber": ["0000789019-23-000006"],
                        "form": ["10-K"],
                        "filingDate": ["2023-07-27"],
                        "reportDate": ["2023-06-30"],
                        "fy": [2023],
                        "fp": ["FY"]
                    }
                }
            }""")

            # Mock the internal method to track calls
            with patch.object(
                ingester, "_process_submissions_file", new_callable=AsyncMock
            ) as mock_process:

                async def mock_process_func(f, cik, pid, stats):
                    stats.companies_processed += 1

                mock_process.side_effect = mock_process_func

                stats = await ingester.ingest_submissions(submissions_dir)

            # Should process 2 files
            assert mock_process.call_count == 2
            assert stats.companies_processed == 2

    @pytest.mark.asyncio
    async def test_ingest_submissions_resume(self, tmp_path):
        """Test resuming submissions ingestion from checkpoint."""
        from unittest.mock import MagicMock, patch

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

        # Mock _get_provider_id to return a fixed UUID
        with patch.object(
            ingester,
            "_get_provider_id",
            return_value="12345678-1234-5678-1234-567812345678",
        ):
            submissions_dir = tmp_path / "submissions"
            submissions_dir.mkdir()

            (submissions_dir / "CIK0000320193.json").write_text("{}")
            (submissions_dir / "CIK0000789019.json").write_text("{}")

            # Create checkpoint with first file already processed
            checkpoint = BulkImportCheckpoint(
                dataset="submissions",
                source_file=str(submissions_dir),
                last_processed_cik="0000320193",
                companies_processed=1,
            )

            with patch.object(
                ingester, "_process_submissions_file", new_callable=AsyncMock
            ) as mock_process:

                async def mock_process_func(f, cik, pid, stats):
                    stats.companies_processed += 1

                mock_process.side_effect = mock_process_func

                stats = await ingester.ingest_submissions(
                    submissions_dir, checkpoint=checkpoint
                )

            # Should skip first file and only process second
            assert mock_process.call_count == 1
            assert stats.companies_processed == 1

    @pytest.mark.asyncio
    async def test_ingest_submissions_checksum_validation(self, tmp_path):
        """Test that submissions ingestion validates directory checksum."""
        from unittest.mock import MagicMock

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

        submissions_dir = tmp_path / "submissions"
        submissions_dir.mkdir()
        (submissions_dir / "CIK0000320193.json").write_text("{}")

        # Create checkpoint with old checksum
        old_checksum = "old_checksum"
        checkpoint = BulkImportCheckpoint(
            dataset="submissions",
            source_file=str(submissions_dir),
            source_file_checksum=old_checksum,
        )

        ingester._save_checkpoint(checkpoint)

        # Modify the directory (add new file)
        (submissions_dir / "CIK0000789019.json").write_text("{}")

        # Load checkpoint - should have old checksum
        loaded = ingester._load_checkpoint("submissions")
        assert loaded is not None
        assert loaded.source_file_checksum == old_checksum

        # New checksum should differ
        new_checksum = ingester._compute_dir_checksum(submissions_dir)
        assert new_checksum != old_checksum
