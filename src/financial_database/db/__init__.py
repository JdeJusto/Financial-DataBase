"""Database repository abstractions for the financial-database project.

All repositories use parameterized SQL with psycopg3.
They support transactions and idempotent operations.
"""

from financial_database.db.connection import get_connection
from financial_database.db.repositories import (
    CompanyIdentifierRepository,
    CompanyListingRepository,
    CompanyRepository,
    DividendRepository,
    ExchangeRepository,
    FilingRepository,
    FinancialFactRepository,
    ImportRunRepository,
    PriceRepository,
    RawDocumentRepository,
    SplitRepository,
)

__all__ = [
    "CompanyIdentifierRepository",
    "CompanyListingRepository",
    "CompanyRepository",
    "DividendRepository",
    "ExchangeRepository",
    "FilingRepository",
    "FinancialFactRepository",
    "ImportRunRepository",
    "PriceRepository",
    "RawDocumentRepository",
    "SplitRepository",
]