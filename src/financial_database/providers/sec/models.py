"""SEC EDGAR models for company universe, submissions, and company facts."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class SECCompany:
    """SEC company from company tickers exchange reference."""

    cik: str
    name: str
    ticker: str | None = None
    exchange: str | None = None
    sic: str | None = None
    sic_description: str | None = None
    owner_org: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def normalized_cik(self) -> str:
        """Return CIK normalized to 10-digit zero-padded format."""
        return normalize_cik(self.cik)


@dataclass
class SECFiling:
    """SEC filing metadata from submissions."""

    accession_number: str
    form: str
    filing_date: date | None = None
    period_end: date | None = None
    period_start: date | None = None
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    filing_url: str | None = None
    is_amended: bool = False
    primary_document: str | None = None
    primary_doc_description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def normalized_accession(self) -> str:
        """Return accession number in canonical format (no dashes)."""
        return normalize_accession_number(self.accession_number)


@dataclass
class SECSubmissions:
    """SEC submissions response for a company."""

    cik: str
    entity_name: str
    filings: list[SECFiling] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def normalized_cik(self) -> str:
        return normalize_cik(self.cik)


@dataclass
class SECCompanyFact:
    """Individual fact from CompanyFacts XBRL data."""

    concept: str
    namespace: str
    label: str | None = None
    unit: str = ""
    values: list["SECCompanyFactValue"] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SECCompanyFactValue:
    """A single fact value with period and filing context."""

    value: int | float
    period_start: date | None
    period_end: date
    unit: str | None = None
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    form: str | None = None
    filing_date: date | None = None
    accession_number: str | None = None
    frame: str | None = None
    is_instant: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SECCompanyFacts:
    """SEC CompanyFacts XBRL response."""

    cik: str
    entity_name: str
    facts: dict[str, dict[str, SECCompanyFact]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def normalized_cik(self) -> str:
        return normalize_cik(self.cik)


@dataclass
class ExchangeMapping:
    """Mapping from SEC exchange to internal exchange."""

    sec_exchange: str
    internal_code: str
    internal_name: str
    mic: str | None = None
    country: str = "USA"
    timezone: str = "America/New_York"
    currency: str = "USD"


# Canonical exchange mapping table
SEC_EXCHANGE_MAPPINGS: list[ExchangeMapping] = [
    ExchangeMapping("NASDAQ", "NASDAQ", "NASDAQ Stock Market", "XNAS"),
    ExchangeMapping("NYSE", "NYSE", "New York Stock Exchange", "XNYS"),
    ExchangeMapping("NYSE American", "NYSEAMERICAN", "NYSE American", "XASE"),
    ExchangeMapping("NYSE Arca", "NYSEARCA", "NYSE Arca", "ARCX"),
    ExchangeMapping("BATS", "BATS", "BATS Exchange", "BATS"),
    ExchangeMapping("OTC", "OTC", "OTC Markets", None),
    ExchangeMapping("OTCQB", "OTCQB", "OTCQB Market", None),
    ExchangeMapping("OTCQX", "OTCQX", "OTCQX Market", None),
    ExchangeMapping("PINK", "PINK", "Pink Sheets", None),
]

SEC_EXCHANGE_MAP = {m.sec_exchange: m for m in SEC_EXCHANGE_MAPPINGS}


def normalize_cik(cik: str | int) -> str:
    """Normalize CIK to 10-digit zero-padded string.

    SEC CIKs are 10 digits with leading zeros. Preserve canonical format.
    """
    if isinstance(cik, int):
        cik_str = str(cik)
    else:
        cik_str = str(cik).strip().lstrip("0")
        if not cik_str:
            cik_str = "0"
    return cik_str.zfill(10)


def normalize_accession_number(accession: str) -> str:
    """Normalize accession number to canonical format (no dashes).

    SEC accession format: 0000320193-23-000106
    Canonical: 000032019323000106
    """
    return accession.replace("-", "").strip()


def normalize_exchange(sec_exchange: str | None) -> ExchangeMapping | None:
    """Map SEC exchange name to internal exchange mapping.

    Returns None if no confident mapping exists.
    """
    if not sec_exchange:
        return None
    # Case-insensitive lookup
    sec_exchange_clean = sec_exchange.strip()
    for key, mapping in SEC_EXCHANGE_MAP.items():
        if key.lower() == sec_exchange_clean.lower():
            return mapping
    return None


def get_exchange_mappings() -> list[ExchangeMapping]:
    """Get all known SEC exchange mappings for seeding exchanges table."""
    return SEC_EXCHANGE_MAPPINGS


_US_EXCHANGE_CODES = {
    "NASDAQ",
    "NYSE",
    "NYSE AMERICAN",
    "NYSE ARCA",
    "BATS",
    "CBOE",
    "OTC",
    "OTCQB",
    "OTCQX",
    "PINK",
}


def infer_country(sec_exchange: str | None) -> str:
    """Infer a company's country from its SEC exchange (best effort).

    The SEC tickers file does not carry country. Known US exchanges map to
    'USA', other non-empty exchanges map to 'FOREIGN', and a missing exchange
    maps to 'UNKNOWN'.
    """
    if not sec_exchange or not sec_exchange.strip():
        return "UNKNOWN"
    if sec_exchange.strip().upper() in _US_EXCHANGE_CODES:
        return "USA"
    return "FOREIGN"
