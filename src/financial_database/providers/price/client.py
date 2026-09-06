"""
Stooq client for fetching stock price data.
Stooq provides free CSV data for stocks, indices, forex, etc.
URL format: https://stooq.com/q/d/l/?s=<symbol>&i=d
Where <symbol> is the stock symbol in Stooq format (e.g., aapl.us for Apple)
&i=d means daily data.
"""

import csv
import logging
from datetime import datetime, date
from typing import Dict, List, Optional
from urllib.parse import urlencode

import httpx

from financial_database.providers.base import BaseHTTPClient, ImportResult
from financial_database.providers.sec.client import SECClient  # For logging pattern, but we'll create our own

logger = logging.getLogger(__name__)

class StooqClient(BaseHTTPClient):
    """
    Client for fetching data from Stooq.
    Stooq does not require an API key for basic data.
    """

    BASE_URL = "https://stooq.com/q/d/l/"

    # Mapping of exchange codes to Stooq suffixes.
    # We'll map common exchange codes to their Stooq suffix.
    # For US exchanges (NYSE, NASDAQ, etc.), we use '.us'
    # For OTC markets, we use specific suffixes.
    EXCHANGE_SUFFIX_MAP = {
        'NYSE': 'us',
        'NASDAQ': 'us',
        'AMEX': 'us',
        'ARCA': 'us',
        'BATS': 'us',
        'NYSEAMERICAN': 'us',
        'NYSEARCA': 'us',
        'OTC': 'otc',
        'OTCQB': 'otcqb',
        'OTCQX': 'otcqx',
        'PINK': 'pink',
        # For non-US, we might need to map to the country code or specific suffix.
        # For now, we'll only support US exchanges and log warnings for others.
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Stooq does not require a special User-Agent, but we'll set one to be polite.
        self.headers.update({
            'User-Agent': 'financial-database/1.0 (+https://github.com/yourorg/financial-database)'
        })

    @property
    def name(self) -> str:
        return "Stooq"

    @property
    def provider_type(self) -> str:
        return "price"

    def validate_config(self) -> None:
        # No configuration to validate for Stooq
        pass

    async def import_data(self, *args, **kwargs) -> ImportResult:
        # This client is not used for direct import via the provider interface.
        # The StooqImporter uses the client to fetch data and then inserts via repositories.
        raise NotImplementedError("StooqClient does not support import_data via provider interface.")

    def get_symbol(self, ticker: str, exchange_code: str) -> Optional[str]:
        """
        Convert ticker and exchange code to Stooq symbol.
        Returns None if the exchange is not supported.
        """
        suffix = self.EXCHANGE_SUFFIX_MAP.get(exchange_code.upper())
        if suffix is None:
            logger.warning(f"No Stooq suffix mapping for exchange code: {exchange_code}")
            return None
        # Stooq symbol format: <ticker>.<suffix>
        # Ticker should be lowercase.
        return f"{ticker.lower()}.{suffix}"

    async def fetch_daily_data(self, symbol: str) -> List[Dict]:
        """
        Fetch daily historical data for a given Stooq symbol.
        Returns a list of dictionaries, each representing a row of data.
        """
        params = {
            's': symbol,
            'i': 'd',  # daily
        }
        url = f"{self.BASE_URL}?{urlencode(params)}"
        logger.debug(f"Fetching Stooq data for symbol {symbol} from {url}")

        response = await self.get(url)
        response.raise_for_status()

        # Stooq returns CSV data with a header.
        # We'll parse the CSV.
        lines = response.text.strip().split('\n')
        if not lines:
            return []

        reader = csv.DictReader(lines)
        data = []
        for row in reader:
            # Stooq column names: Date, Open, High, Low, Close, Volume
            # We'll convert to our expected format.
            try:
                data.append({
                    'date': row['Date'],
                    'open': float(row['Open']) if row['Open'] else None,
                    'high': float(row['High']) if row['High'] else None,
                    'low': float(row['Low']) if row['Low'] else None,
                    'close': float(row['Close']) if row['Close'] else None,
                    'volume': int(row['Volume']) if row['Volume'] else None,
                })
            except (ValueError, KeyError) as e:
                logger.warning(f"Error parsing Stooq row for symbol {symbol}: {row}. Error: {e}")
                continue

        return data

    async def fetch_latest_data(self, symbol: str) -> Optional[Dict]:
        """
        Fetch the latest data point for a symbol.
        We'll fetch the last 5 days and take the most recent.
        """
        data = await self.fetch_daily_data(symbol)
        if not data:
            return None
        # Stooq returns data in descending order? Let's check: actually, Stooq returns ascending by date (oldest first).
        # We'll take the last row as the most recent.
        return data[-1] if data else None