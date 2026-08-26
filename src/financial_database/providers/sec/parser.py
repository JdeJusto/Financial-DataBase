"""SEC EDGAR parser for normalizing raw SEC data into domain models."""

import logging
from dataclasses import dataclass, field
from datetime import date

from financial_database.providers.sec.models import (
    ExchangeMapping,
    SECCompany,
    SECCompanyFacts,
    SECSubmissions,
    normalize_accession_number,
    normalize_cik,
    normalize_exchange,
)

logger = logging.getLogger(__name__)


@dataclass
class ParsedCompany:
    """Normalized company ready for database insertion."""

    cik: str
    legal_name: str
    country: str | None = "USA"
    sector: str | None = None
    industry: str | None = None
    currency: str = "USD"
    website: str | None = None
    is_active: bool = True
    identifiers: dict[str, str] = field(default_factory=dict)
    listings: list["ParsedListing"] = field(default_factory=list)


@dataclass
class ParsedListing:
    """Normalized listing ready for database insertion."""

    exchange_code: str
    exchange_name: str
    ticker: str
    share_class: str | None = None
    listing_date: date | None = None
    delisting_date: date | None = None
    is_primary: bool = False
    mic: str | None = None
    country: str = "USA"
    timezone: str = "America/New_York"
    currency: str = "USD"


@dataclass
class ParsedFiling:
    """Normalized filing ready for database insertion."""

    accession_number: str
    form: str
    filing_date: date | None = None
    period_start: date | None = None
    period_end: date | None = None
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    filing_url: str | None = None
    is_amended: bool = False
    raw_document_id: str | None = None


@dataclass
class ParsedFinancialFact:
    """Normalized financial fact ready for database insertion."""

    concept: str
    namespace: str
    value: float
    unit: str
    period_start: date | None
    period_end: date
    fiscal_year: int
    fiscal_period: str
    provider_id: str
    source_id: str | None = None
    filing_id: str | None = None
    form: str | None = None
    filing_date: date | None = None
    frame: str | None = None
    is_instant: bool = False


class SECParser:
    """Parse and normalize SEC data into domain models."""

    def __init__(self) -> None:
        self._exchange_cache: dict[str, ExchangeMapping | None] = {}

    def parse_company(self, sec_company: SECCompany) -> ParsedCompany:
        """Parse SEC company into normalized domain model."""
        parsed = ParsedCompany(
            cik=normalize_cik(sec_company.cik),
            legal_name=sec_company.name.strip(),
            country="USA",
            currency="USD",
        )

        # Add CIK as primary identifier
        parsed.identifiers["CIK"] = parsed.cik

        # Add ticker if available
        if sec_company.ticker:
            parsed.identifiers["TICKER"] = sec_company.ticker.upper()

        # Create listing if ticker and exchange available
        if sec_company.ticker and sec_company.exchange:
            mapping = self._get_exchange_mapping(sec_company.exchange)
            if mapping:
                listing = ParsedListing(
                    exchange_code=mapping.internal_code,
                    exchange_name=mapping.internal_name,
                    ticker=sec_company.ticker.upper(),
                    mic=mapping.mic,
                    country=mapping.country,
                    timezone=mapping.timezone,
                    currency=mapping.currency,
                    is_primary=True,
                )
                parsed.listings.append(listing)
            else:
                logger.warning(
                    "Unknown SEC exchange, listing not created",
                    extra={"cik": parsed.cik, "exchange": sec_company.exchange},
                )

        return parsed

    def parse_filings(self, submissions: SECSubmissions) -> list[ParsedFiling]:
        """Parse SEC submissions into normalized filings."""
        parsed_filings: list[ParsedFiling] = []
        for filing in submissions.filings:
            # Only process financial reporting forms
            if not self._is_financial_form(filing.form):
                continue

            # Allow filings without period_end (SEC may not provide period_of_report)
            # period_end is now nullable in the database
            parsed = ParsedFiling(
                accession_number=normalize_accession_number(filing.accession_number),
                form=filing.form,
                filing_date=filing.filing_date,
                period_start=filing.period_start,
                period_end=filing.period_end,  # Can be None
                fiscal_year=filing.fiscal_year,
                fiscal_period=filing.fiscal_period or "FY",
                filing_url=filing.filing_url,
                is_amended=filing.is_amended,
            )
            parsed_filings.append(parsed)

        return parsed_filings

    def parse_company_facts(
        self,
        company_facts: SECCompanyFacts,
        filing_id_map: dict[str, str] | None = None,
    ) -> list[ParsedFinancialFact]:
        """Parse SEC CompanyFacts into normalized financial facts.

        Args:
            company_facts: Parsed SEC CompanyFacts data
            filing_id_map: Optional mapping from accession_number to internal filing_id

        Returns:
            List of normalized financial facts
        """
        facts = []
        cik = normalize_cik(company_facts.cik)

        for namespace, concepts in company_facts.facts.items():
            for concept_name, fact in concepts.items():
                for value in fact.values:
                    # Determine fiscal year/period
                    fiscal_year = value.fiscal_year
                    fiscal_period = value.fiscal_period or "FY"

                    # If missing, try to infer from period_end
                    if fiscal_year is None and value.period_end:
                        fiscal_year = value.period_end.year

                    if fiscal_year is None:
                        logger.warning(
                            "Skipping fact with no fiscal year",
                            extra={
                                "cik": cik,
                                "concept": concept_name,
                                "namespace": namespace,
                            },
                        )
                        continue

                    # Build source_id from accession + concept + period
                    source_parts = []
                    if value.accession_number:
                        source_parts.append(
                            normalize_accession_number(value.accession_number)
                        )
                    source_parts.append(f"{namespace}:{concept_name}")
                    if value.period_start:
                        source_parts.append(value.period_start.isoformat())
                    source_parts.append(value.period_end.isoformat())
                    source_id = "|".join(source_parts)

                    # Look up filing_id from accession
                    filing_id = None
                    if value.accession_number and filing_id_map:
                        filing_id = filing_id_map.get(
                            normalize_accession_number(value.accession_number)
                        )

                    # Convert value to float, skip non-numeric
                    try:
                        numeric_value = float(value.value)
                    except (ValueError, TypeError):
                        logger.warning(
                            "Skipping non-numeric fact value",
                            extra={
                                "cik": cik,
                                "concept": concept_name,
                                "namespace": namespace,
                                "value": value.value,
                            },
                        )
                        continue

                    parsed = ParsedFinancialFact(
                        concept=concept_name,
                        namespace=namespace,
                        value=numeric_value,
                        unit=fact.unit or value.metadata.get("unit", "USD"),
                        period_start=value.period_start
                        if not value.is_instant
                        else None,
                        period_end=value.period_end,
                        fiscal_year=fiscal_year,
                        fiscal_period=fiscal_period,
                        provider_id="",  # Will be filled by importer
                        source_id=source_id,
                        filing_id=filing_id,
                        form=value.form,
                        filing_date=value.filing_date,
                        frame=value.frame,
                        is_instant=value.is_instant,
                    )
                    facts.append(parsed)

        logger.info(
            "Parsed company facts",
            extra={
                "cik": cik,
                "fact_count": len(facts),
                "namespace_count": len(company_facts.facts),
            },
        )
        return facts

    def _get_exchange_mapping(self, sec_exchange: str) -> ExchangeMapping | None:
        """Get exchange mapping with caching."""
        if sec_exchange not in self._exchange_cache:
            self._exchange_cache[sec_exchange] = normalize_exchange(sec_exchange)
        return self._exchange_cache[sec_exchange]

    def _is_financial_form(self, form: str) -> bool:
        """Check if form is a financial reporting form."""
        financial_forms = {
            "10-K",
            "10-K/A",
            "10-Q",
            "10-Q/A",
            "20-F",
            "20-F/A",
            "40-F",
            "40-F/A",
            "6-K",
            "6-K/A",
            "8-K",
            "8-K/A",  # Sometimes contains financial info
        }
        return form in financial_forms


def validate_financial_fact(fact: ParsedFinancialFact) -> list[str]:
    """Validate a financial fact, return list of errors (empty if valid)."""
    errors = []

    if not fact.concept or not fact.concept.strip():
        errors.append("concept is required")

    if not fact.namespace or not fact.namespace.strip():
        errors.append("namespace is required")

    if fact.value is None:
        errors.append("value is required")

    if not fact.unit or not fact.unit.strip():
        errors.append("unit is required")

    if fact.period_end is None:
        errors.append("period_end is required")

    if fact.fiscal_year is None or fact.fiscal_year < 1900 or fact.fiscal_year > 2100:
        errors.append("fiscal_year must be valid")

    if not fact.fiscal_period or not fact.fiscal_period.strip():
        errors.append("fiscal_period is required")

    if fact.period_start and fact.period_end and fact.period_start > fact.period_end:
        errors.append("period_start must be <= period_end")

    if fact.is_instant and fact.period_start is not None:
        errors.append("instant facts must have period_start = NULL")

    if not fact.is_instant and fact.period_start is None:
        errors.append("duration facts must have period_start != NULL")

    return errors
