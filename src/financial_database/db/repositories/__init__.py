"""Repository packages for the financial-database project.

All repositories use parameterized SQL with psycopg3.
They support transactions and idempotent operations.
"""

from financial_database.db.repositories.company_identifier_repository import (
    CompanyIdentifierRepository,
)
from financial_database.db.repositories.company_listing_repository import (
    CompanyListingRepository,
)
from financial_database.db.repositories.company_repository import CompanyRepository
from financial_database.db.repositories.dividend_repository import DividendRepository
from financial_database.db.repositories.exchange_repository import ExchangeRepository
from financial_database.db.repositories.filing_repository import FilingRepository
from financial_database.db.repositories.financial_fact_repository import (
    FinancialFactRepository,
)
from financial_database.db.repositories.import_run_repository import ImportRunRepository
from financial_database.db.repositories.price_repository import PriceRepository
from financial_database.db.repositories.raw_document_repository import (
    RawDocumentRepository,
)
from financial_database.db.repositories.split_repository import SplitRepository

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
