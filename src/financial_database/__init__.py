"""Financial Database - PostgreSQL-first financial data platform."""

__version__ = "0.3.0"

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
from financial_database.providers.sec import (
    ImportStats,
    SECClient,
    SECCompany,
    SECCompanyFacts,
    SECFiling,
    SECImporter,
    SECSubmissions,
    create_sec_importer,
    normalize_accession_number,
    normalize_cik,
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
    # SEC Provider
    "SECClient",
    "SECImporter",
    "ImportStats",
    "create_sec_importer",
    "SECCompany",
    "SECSubmissions",
    "SECFiling",
    "SECCompanyFacts",
    "normalize_cik",
    "normalize_accession_number",
]