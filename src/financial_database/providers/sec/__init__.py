"""SEC EDGAR provider package."""

from financial_database.providers.sec.client import (
    SECClient,
    SECClientError,
    SECNotFoundError,
    SECRateLimitError,
    SECServerError,
)
from financial_database.providers.sec.importer import (
    ImportStats,
    SECImporter,
    create_sec_importer,
)
from financial_database.providers.sec.models import (
    ExchangeMapping,
    SECCompany,
    SECCompanyFact,
    SECCompanyFacts,
    SECCompanyFactValue,
    SECFiling,
    SECSubmissions,
    get_exchange_mappings,
    normalize_accession_number,
    normalize_cik,
    normalize_exchange,
)
from financial_database.providers.sec.parser import (
    ParsedCompany,
    ParsedFiling,
    ParsedFinancialFact,
    SECParser,
    validate_financial_fact,
)

__all__ = [
    # Client
    "SECClient",
    "SECClientError",
    "SECRateLimitError",
    "SECNotFoundError",
    "SECServerError",
    # Importer
    "SECImporter",
    "ImportStats",
    "create_sec_importer",
    # Models
    "SECCompany",
    "SECSubmissions",
    "SECFiling",
    "SECCompanyFact",
    "SECCompanyFactValue",
    "SECCompanyFacts",
    "ExchangeMapping",
    "normalize_cik",
    "normalize_accession_number",
    "normalize_exchange",
    "get_exchange_mappings",
    # Parser
    "SECParser",
    "ParsedCompany",
    "ParsedFiling",
    "ParsedFinancialFact",
    "validate_financial_fact",
]