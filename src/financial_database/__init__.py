"""Financial Database - PostgreSQL-first financial data platform."""

__version__ = "0.2.0"

from financial_database.db.connection import get_connection
from financial_database.db.repositories import (
    CompanyRepository,
    CompanyIdentifierRepository,
    ExchangeRepository,
    CompanyListingRepository,
    FilingRepository,
    FinancialFactRepository,
    PriceRepository,
    DividendRepository,
    SplitRepository,
    ImportRunRepository,
    RawDocumentRepository,
)

__all__ = [
    "get_connection",
    "CompanyRepository",
    "CompanyIdentifierRepository",
    "ExchangeRepository",
    "CompanyListingRepository",
    "FilingRepository",
    "FinancialFactRepository",
    "PriceRepository",
    "DividendRepository",
    "SplitRepository",
    "ImportRunRepository",
    "RawDocumentRepository",
]