"""Financial database models."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImportStats:
    """Statistics for an import operation."""

    # General counters (used by price importer and others)
    records_processed: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_skipped: int = 0

    # SEC-specific counters (used by SEC importer)
    companies_processed: int = 0
    companies_inserted: int = 0
    companies_updated: int = 0
    identifiers_inserted: int = 0
    listings_inserted: int = 0
    listings_updated: int = 0
    exchanges_inserted: int = 0
    filings_processed: int = 0
    filings_inserted: int = 0
    filings_skipped: int = 0
    facts_processed: int = 0
    facts_inserted: int = 0
    facts_skipped: int = 0
    facts_validation_errors: int = 0
    raw_documents_created: int = 0

    # Errors encountered during import
    errors: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "records_processed": self.records_processed,
            "records_inserted": self.records_inserted,
            "records_updated": self.records_updated,
            "records_skipped": self.records_skipped,
            "companies_processed": self.companies_processed,
            "companies_inserted": self.companies_inserted,
            "companies_updated": self.companies_updated,
            "identifiers_inserted": self.identifiers_inserted,
            "listings_inserted": self.listings_inserted,
            "listings_updated": self.listings_updated,
            "exchanges_inserted": self.exchanges_inserted,
            "filings_processed": self.filings_processed,
            "filings_inserted": self.filings_inserted,
            "filings_skipped": self.filings_skipped,
            "facts_processed": self.facts_processed,
            "facts_inserted": self.facts_inserted,
            "facts_skipped": self.facts_skipped,
            "facts_validation_errors": self.facts_validation_errors,
            "raw_documents_created": self.raw_documents_created,
            "errors": self.errors,
        }
