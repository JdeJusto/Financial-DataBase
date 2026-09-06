"""
Yahoo Finance client for fetching stock price data.
Uses yfinance library which provides free access to Yahoo Finance data.
"""

import logging
from datetime import date, datetime
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

from financial_database.providers.base import BaseHTTPClient, ImportResult

logger = logging.getLogger(__name__)


class YFinanceClient(BaseHTTPClient):
    """
    Client for fetching data from Yahoo Finance via yfinance library.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # yfinance handles its own headers/User-Agent

    @property
    def name(self) -> str:
        return "Yahoo Finance"

    @property
    def provider_type(self) -> str:
        return "price"

    def validate_config(self) -> None:
        # No configuration to validate for yfinance
        pass

    async def import_data(self, *args, **kwargs) -> ImportResult:
        # This client is not used for direct import via the provider interface.
        # The YFinanceImporter uses the client to fetch data and then inserts via repositories.
        raise NotImplementedError("YFinanceClient does not support import_data via provider interface.")

    def get_symbol(self, ticker: str, exchange_code: str) -> Optional[str]:
        """
        Convert ticker and exchange code to Yahoo Finance symbol.
        For US stocks, Yahoo Finance uses the ticker directly (e.g., AAPL).
        For non-US stocks, it may require suffixes like .L for London, etc.
        For now, we'll only support US exchanges and return ticker as-is.
        """
        # For simplicity, we'll just return the ticker for US exchanges
        # In a more complete implementation, we'd map exchange codes to appropriate suffixes
        us_exchanges = {'NYSE', 'NASDAQ', 'AMEX', 'ARCA', 'BATS', 'NYSEAMERICAN', 'NYSEARCA'}
        if exchange_code.upper() in us_exchanges:
            return ticker.upper()
        else:
            logger.warning(f"No Yahoo Finance symbol mapping for exchange code: {exchange_code}")
            return None

    async def fetch_daily_data(self, symbol: str) -> List[Dict]:
        """
        Fetch daily historical data for a given symbol using yfinance.
        Returns a list of dictionaries, each representing a row of data.
        """
        try:
            # Fetch data for the last 5 days to ensure we get recent data
            ticker_obj = yf.Ticker(symbol)
            # Get history for the last 10 days to account for weekends/holidays
            hist = ticker_obj.history(period="10d")

            if hist.empty:
                logger.warning(f"No historical data returned for symbol {symbol}")
                return []

            # Convert DataFrame to list of dictionaries
            data = []
            for date, row in hist.iterrows():
                # Convert Timestamp to date string
                date_str = date.strftime('%Y-%m-%d')
                data.append({
                    'date': date_str,
                    'open': float(row['Open']) if not pd.isna(row['Open']) else None,
                    'high': float(row['High']) if not pd.isna(row['High']) else None,
                    'low': float(row['Low']) if not pd.isna(row['Low']) else None,
                    'close': float(row['Close']) if not pd.isna(row['Close']) else None,
                    'volume': int(row['Volume']) if not pd.isna(row['Volume']) else None,
                })

            return data
        except Exception as e:
            logger.error(f"Error fetching data for symbol {symbol}: {e}")
            return []

    async def fetch_latest_data(self, symbol: str) -> Optional[Dict]:
        """
        Fetch the latest data point for a symbol.
        We'll fetch the last 5 days and take the most recent.
        """
        data = await self.fetch_daily_data(symbol)
        if not data:
            return None
        # yfinance returns data in descending order (most recent first)
        # So we take the first row
        return data[0] if data else None