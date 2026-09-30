"""Financial Database - PostgreSQL-first financial data platform."""

__version__ = "0.1.0"

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
    "CompanyIdentifierRepository",
    "CompanyListingRepository",
    "CompanyRepository",
    "DividendRepository",
    "ExchangeRepository",
    "FilingRepository",
    "FinancialFactRepository",
    "ImportRunRepository",
    "ImportStats",
    "PriceRepository",
    "RawDocumentRepository",
    "SECClient",
    "SECCompany",
    "SECCompanyFacts",
    "SECFiling",
    "SECImporter",
    "SECSubmissions",
    "SplitRepository",
    "create_sec_importer",
    "get_connection",
    "normalize_accession_number",
    "normalize_cik",
]
