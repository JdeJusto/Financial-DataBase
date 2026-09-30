"""
Stooq price importer.
Fetches stock price data from Stooq and inserts into the prices table.
"""

import logging
import os

import psycopg

from financial_database.db.repositories.company_listing_repository import (
    CompanyListingRepository,
)
from financial_database.db.repositories.company_repository import CompanyRepository
from financial_database.db.repositories.data_provider_repository import (
    DataProviderRepository,
)
from financial_database.db.repositories.exchange_repository import ExchangeRepository
from financial_database.db.repositories.import_run_repository import ImportRunRepository
from financial_database.db.repositories.price_repository import PriceRepository
from financial_database.models import ImportStats
from financial_database.providers.price.client import StooqClient

logger = logging.getLogger(__name__)


class StooqImporter:
    """
    Importer for Stooq stock price data.
    """

    def __init__(
        self,
        database_url: str | None = None,
        conn: psycopg.Connection | None = None,
        client: StooqClient | None = None,
        company_repo: CompanyRepository | None = None,
        listing_repo: CompanyListingRepository | None = None,
        provider_repo: DataProviderRepository | None = None,
        price_repo: PriceRepository | None = None,
        exchange_repo: ExchangeRepository | None = None,
        import_run_repo: ImportRunRepository | None = None,
    ):
        # Determine the database connection
        if conn is not None:
            self.conn = conn
        elif database_url is not None:
            self.conn = psycopg.connect(database_url, row_factory=psycopg.rows.dict_row)
        else:
            # Use default connection from environment
            self.conn = psycopg.connect(
                os.environ.get(
                    "DATABASE_URL",
                    "postgresql://financial:test@localhost:5432/financial_database",
                ),
                row_factory=psycopg.rows.dict_row,
            )

        if self.conn is None:
            raise RuntimeError(
                "Failed to establish database connection for StooqImporter"
            )

        # Set up dependencies, injecting the connection into repositories if not provided
        self.client = client or StooqClient()
        self.company_repo = company_repo or CompanyRepository(self.conn)
        self.listing_repo = listing_repo or CompanyListingRepository(self.conn)
        self.provider_repo = provider_repo or DataProviderRepository(self.conn)
        self.price_repo = price_repo or PriceRepository(self.conn)
        self.exchange_repo = exchange_repo or ExchangeRepository(self.conn)
        self.import_runs = import_run_repo or ImportRunRepository(self.conn)

    async def get_or_create_provider(self) -> dict:
        """
        Get or create the Stooq data provider.
        Returns the provider record.
        """
        provider = self.provider_repo.get_by_name("Stooq")
        if provider:
            return provider

        # Create the provider if it doesn't exist
        provider_data = {
            "name": "Stooq",
            "type": "price",
            "display_name": "Stooq",
            "base_url": "https://stooq.com",
            "is_active": True,
        }
        provider = self.provider_repo.create(provider_data)
        logger.info("Created Stooq data provider")
        return provider

    async def update_prices_for_listing(
        self,
        listing: dict,
        provider_id: str,
        stats: ImportStats,
    ) -> None:
        """
        Update prices for a single company listing.
        """
        ticker = listing["ticker"]
        exchange_id = listing["exchange_id"]

        # Get exchange by ID to get its code
        exchange = self.exchange_repo.get(exchange_id)
        if not exchange:
            logger.warning(f"No exchange found for ID {exchange_id}")
            stats.records_skipped += 1
            return

        exchange_code = exchange["code"]
        symbol = self.client.get_symbol(ticker, exchange_code)
        if not symbol:
            logger.warning(
                f"Could not generate Stooq symbol for {ticker} on exchange {exchange_code}"
            )
            stats.records_skipped += 1
            return

        # Fetch latest data
        try:
            latest_data = await self.client.fetch_latest_data(symbol)
        except Exception as e:  # noqa: BLE001 — per-record boundary: skip and continue
            logger.error(f"Error fetching data for symbol {symbol}: {e}")
            stats.records_skipped += 1
            return

        if not latest_data:
            logger.warning(f"No data returned for symbol {symbol}")
            stats.records_skipped += 1
            return

        # Check if we already have this price (by listing_id and price_date)
        # We'll rely on the unique constraint in the prices table to avoid duplicates.
        # We'll try to insert and catch duplicates, or we can check first.
        # For simplicity, we'll attempt to insert and if it fails due to unique constraint, we'll skip.

        price_date = latest_data["date"]
        # Convert string to date object if needed
        if isinstance(price_date, str):
            # Stooq date format is YYYY-MM-DD
            from datetime import date

            price_date = date.fromisoformat(price_date)

        price_data = {
            "listing_id": listing["id"],
            "provider_id": provider_id,
            "price_date": price_date,
            "open": latest_data["open"],
            "high": latest_data["high"],
            "low": latest_data["low"],
            "close": latest_data["close"],
            "volume": latest_data["volume"],
            "currency": "USD",  # Stooq primarily provides USD prices for US stocks; we assume USD for now.
            "source_id": f"stooq:{symbol}",  # Unique identifier for the price record from Stooq
        }

        try:
            await self.price_repo.create(price_data)
            stats.records_inserted += 1
            logger.debug(f"Inserted price for {ticker} on {price_date}")
        except Exception as e:  # noqa: BLE001 — duplicate detection needs the driver error text
            # Check if it's a duplicate key violation
            if (
                "unique constraint" in str(e).lower()
                or "duplicate key" in str(e).lower()
            ):
                stats.records_skipped += 1
                logger.debug(f"Duplicate price for {ticker} on {price_date}, skipping")
            else:
                logger.error(f"Error inserting price for {ticker}: {e}")
                stats.records_skipped += 1

    async def run(self, limit: int | None = None) -> ImportStats:
        """
        Run the price update for all listings (or up to limit).
        """
        stats = ImportStats()
        provider = await self.get_or_create_provider()
        provider_id = str(provider["id"])

        # Get all active listings
        listings = self.listing_repo.list_active(limit=limit)
        logger.info(f"Found {len(listings)} active listings to process")

        for listing in listings:
            await self.update_prices_for_listing(listing, provider_id, stats)

        return stats
