"""Database repository abstractions for the financial-database project.

All repositories use parameterized SQL with psycopg3.
They support transactions and idempotent operations.
"""

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