"""Unit tests for Yahoo Finance price ingestion functionality."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import psycopg
from psycopg.rows import dict_row

from financial_database.providers.price.yfinance_importer import YFinanceImporter
from financial_database.providers.price.yfinance_client import YFinanceClient
from financial_database.models import ImportStats


@pytest.fixture
def mock_conn():
    """Create a mock database connection."""
    conn = Mock(spec=psycopg.Connection)
    mock_cursor = Mock()
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=None)
    mock_cursor.fetchone.return_value = {"id": "test-id"}
    conn.cursor.return_value = mock_cursor
    return conn


@pytest.fixture
def mock_client():
    """Create a mock YFinance client."""
    client = Mock(spec=YFinanceClient)
    client.get_symbol.return_value = "AAPL"
    client.fetch_latest_data = AsyncMock(return_value={
        "date": "2026-09-05",
        "open": 150.0,
        "high": 155.0,
        "low": 149.0,
        "close": 153.0,
        "volume": 1000000
    })
    return client


@pytest.fixture
def mock_listing_repo():
    """Create a mock company listing repository."""
    repo = Mock()
    repo.list_active.return_value = [
        {
            "id": "listing-1",
            "ticker": "AAPL",
            "exchange_id": "nasdaq-id",
            "company_id": "company-1"
        }
    ]
    return repo


@pytest.fixture
def mock_exchange_repo():
    """Create a mock exchange repository."""
    repo = Mock()
    repo.get = Mock(return_value={
        "id": "nasdaq-id",
        "code": "NASDAQ",
        "name": "NASDAQ"
    })
    return repo


@pytest.fixture
def mock_provider_repo():
    """Create a mock data provider repository."""
    repo = Mock()
    repo.get_by_name = Mock(return_value=None)
    repo.create = Mock(return_value={
        "id": "provider-yfinance",
        "name": "Yahoo Finance",
        "type": "price",
        "display_name": "Yahoo Finance",
        "base_url": "https://finance.yahoo.com",
        "is_active": True
    })
    return repo


@pytest.fixture
def mock_price_repo():
    """Create a mock price repository."""
    repo = Mock()
    repo.create = Mock()
    return repo


@pytest.fixture
def mock_import_run_repo():
    """Create a mock import run repository."""
    repo = Mock()
    repo.create = Mock(return_value={"id": "run-1"})
    repo.update = Mock()
    return repo


@pytest.mark.asyncio
async def test_yfinance_importer_init(mock_conn):
    """Test YFinanceImporter initialization."""
    importer = YFinanceImporter(conn=mock_conn)
    assert importer.conn == mock_conn
    assert isinstance(importer.client, YFinanceClient)


@pytest.mark.asyncio
async def test_update_prices_for_listing_success(
    mock_conn,
    mock_client,
    mock_listing_repo,
    mock_exchange_repo,
    mock_provider_repo,
    mock_price_repo,
    mock_import_run_repo
):
    """Test successful price update for a listing."""
    # Setup
    importer = YFinanceImporter(
        conn=mock_conn,
        client=mock_client,
        listing_repo=mock_listing_repo,
        exchange_repo=mock_exchange_repo,
        provider_repo=mock_provider_repo,
        price_repo=mock_price_repo,
        import_run_repo=mock_import_run_repo
    )

    stats = ImportStats()
    listing = {
        "id": "listing-1",
        "ticker": "AAPL",
        "exchange_id": "nasdaq-id",
        "company_id": "company-1"
    }
    provider_id = "provider-yfinance"

    # Execute
    await importer.update_prices_for_listing(listing, provider_id, stats)

    # Verify
    assert stats.records_inserted == 1
    mock_client.get_symbol.assert_called_once_with("AAPL", "NASDAQ")
    mock_client.fetch_latest_data.assert_called_once_with("AAPL")
    mock_price_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_update_prices_for_listing_no_exchange(
    mock_conn,
    mock_client,
    mock_listing_repo,
    mock_exchange_repo,
    mock_provider_repo,
    mock_price_repo,
    mock_import_run_repo
):
    """Test price update when exchange is not found."""
    # Setup
    mock_exchange_repo.get.return_value = None
    importer = YFinanceImporter(
        conn=mock_conn,
        client=mock_client,
        listing_repo=mock_listing_repo,
        exchange_repo=mock_exchange_repo,
        provider_repo=mock_provider_repo,
        price_repo=mock_price_repo,
        import_run_repo=mock_import_run_repo
    )

    stats = ImportStats()
    listing = {
        "id": "listing-1",
        "ticker": "AAPL",
        "exchange_id": "unknown-id",
        "company_id": "company-1"
    }
    provider_id = "provider-yfinance"

    # Execute
    await importer.update_prices_for_listing(listing, provider_id, stats)

    # Verify
    assert stats.records_skipped == 1
    mock_price_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_update_prices_for_listing_no_symbol(
    mock_conn,
    mock_client,
    mock_listing_repo,
    mock_exchange_repo,
    mock_provider_repo,
    mock_price_repo,
    mock_import_run_repo
):
    """Test price update when symbol cannot be generated."""
    # Setup
    mock_client.get_symbol.return_value = None
    importer = YFinanceImporter(
        conn=mock_conn,
        client=mock_client,
        listing_repo=mock_listing_repo,
        exchange_repo=mock_exchange_repo,
        provider_repo=mock_provider_repo,
        price_repo=mock_price_repo,
        import_run_repo=mock_import_run_repo
    )

    stats = ImportStats()
    listing = {
        "id": "listing-1",
        "ticker": "AAPL",
        "exchange_id": "nasdaq-id",
        "company_id": "company-1"
    }
    provider_id = "provider-yfinance"

    # Execute
    await importer.update_prices_for_listing(listing, provider_id, stats)

    # Verify
    assert stats.records_skipped == 1
    mock_client.fetch_latest_data.assert_not_called()
    mock_price_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_update_prices_for_listing_duplicate_key(
    mock_conn,
    mock_client,
    mock_listing_repo,
    mock_exchange_repo,
    mock_provider_repo,
    mock_price_repo,
    mock_import_run_repo
):
    """Test price update when duplicate key error occurs."""
    # Setup
    from psycopg.errors import UniqueViolation
    mock_price_repo.create.side_effect = UniqueViolation("duplicate key")

    importer = YFinanceImporter(
        conn=mock_conn,
        client=mock_client,
        listing_repo=mock_listing_repo,
        exchange_repo=mock_exchange_repo,
        provider_repo=mock_provider_repo,
        price_repo=mock_price_repo,
        import_run_repo=mock_import_run_repo
    )

    stats = ImportStats()
    listing = {
        "id": "listing-1",
        "ticker": "AAPL",
        "exchange_id": "nasdaq-id",
        "company_id": "company-1"
    }
    provider_id = "provider-yfinance"

    # Execute
    await importer.update_prices_for_listing(listing, provider_id, stats)

    # Verify
    assert stats.records_skipped == 1
    assert stats.records_inserted == 0


@pytest.mark.asyncio
async def test_run_no_listings(
    mock_conn,
    mock_client,
    mock_listing_repo,
    mock_exchange_repo,
    mock_provider_repo,
    mock_price_repo,
    mock_import_run_repo
):
    """Test run method when no listings are found."""
    # Setup
    mock_listing_repo.list_active.return_value = []
    importer = YFinanceImporter(
        conn=mock_conn,
        client=mock_client,
        listing_repo=mock_listing_repo,
        exchange_repo=mock_exchange_repo,
        provider_repo=mock_provider_repo,
        price_repo=mock_price_repo,
        import_run_repo=mock_import_run_repo
    )

    # Execute
    stats = await importer.run()

    # Verify
    assert stats.records_processed == 0
    assert stats.records_inserted == 0
    assert stats.records_updated == 0
    assert stats.records_skipped == 0


if __name__ == "__main__":
    pytest.main([__file__])