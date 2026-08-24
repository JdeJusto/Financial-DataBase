"""SEC EDGAR bulk ingestion module for processing bulk data files."""

import logging
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import aiofiles
import aiohttp
import ijson
import psycopg

from financial_database.db.repositories import (
    CompanyIdentifierRepository,
    CompanyListingRepository,
    CompanyRepository,
    ExchangeRepository,
    FilingRepository,
    FinancialFactRepository,
    ImportRunRepository,
    RawDocumentRepository,
)
from financial_database.providers.sec.client import (
    SECClient,
)
from financial_database.providers.sec.models import (
    SECCompanyFact,
    SECCompanyFacts,
    SECCompanyFactValue,
)
from financial_database.providers.sec.parser import (
    ParsedFinancialFact,
    SECParser,
    validate_financial_fact,
)

logger = logging.getLogger(__name__)

SEC_BULK_COMPANYFACTS_URL = "https://www.sec.gov/files/companyfacts.zip"
SEC_BULK_SUBMISSIONS_URL = "https://www.sec.gov/files/submissions.zip"
SEC_BULK_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"


@dataclass
class BulkImportStats:
    """Statistics for a bulk import operation."""

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
    errors: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def to_dict(self) -> dict[str, Any]:
        return {
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


@dataclass
class BulkImportCheckpoint:
    """Checkpoint for resuming bulk import."""

    dataset: str  # "companyfacts" or "submissions"
    cik: str | None = None
    last_processed_cik: str | None = None
    companies_processed: int = 0
    facts_processed: int = 0
    filings_processed: int = 0
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "cik": self.cik,
            "last_processed_cik": self.last_processed_cik,
            "companies_processed": self.companies_processed,
            "facts_processed": self.facts_processed,
            "filings_processed": self.filings_processed,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BulkImportCheckpoint":
        return cls(
            dataset=data["dataset"],
            cik=data.get("cik"),
            last_processed_cik=data.get("last_processed_cik"),
            companies_processed=data.get("companies_processed", 0),
            facts_processed=data.get("facts_processed", 0),
            filings_processed=data.get("filings_processed", 0),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


class SECBulkIngester:
    """SEC EDGAR bulk ingester for processing bulk data files."""

    SEC_BULK_COMPANYFACTS_URL = "https://www.sec.gov/files/companyfacts.zip"
    SEC_BULK_SUBMISSIONS_URL = "https://www.sec.gov/files/submissions.zip"
    SEC_BULK_COMPANY_TICKERS_URL = (
        "https://www.sec.gov/files/company_tickers_exchange.json"
    )

    def __init__(
        self,
        conn,
        client,
        parser,
        raw_dir: Path,
        checkpoint_dir: Path | None = None,
        batch_size: int = 100,
    ):
        self.conn = conn
        self.client = client
        self.parser = parser
        self._raw_dir = Path(client._raw_dir)
        self.checkpoint_dir = checkpoint_dir or Path("./data/checkpoints/sec_bulk")
        self.batch_size = 100

        # Repositories

        self.companies = CompanyRepository(conn)
        self.identifiers = CompanyIdentifierRepository(conn)
        self.listings = CompanyListingRepository(conn)
        self.exchanges = ExchangeRepository(conn)
        self.filings = FilingRepository(conn)
        self.facts = FinancialFactRepository(conn)
        self.raw_docs = RawDocumentRepository(conn)
        self.import_runs = ImportRunRepository(conn)

        self._raw_dir = Path(client._raw_dir)
        self.checkpoint_dir = Path(checkpoint_dir or "./data/checkpoints/sec_bulk")
        self.batch_size = 100

        # Provider ID (cached)
        self._provider_id: uuid.UUID | None = None

        # SEC Provider name
        self.SEC_PROVIDER_NAME = "SEC EDGAR"
        self.SEC_PROVIDER_TYPE = "sec"

    def _get_provider_id(self):
        """Get or create SEC provider ID."""

    async def download_bulk_files(self, force: bool = False) -> dict[str, Path]:
        """Download SEC bulk data files."""
        urls = {
            "companyfacts": self.SEC_BULK_COMPANYFACTS_URL,
            "submissions": self.SEC_BULK_SUBMISSIONS_URL,
            "tickers": self.SEC_BULK_COMPANY_TICKERS_URL,
        }

        download_dir = self._raw_dir / "bulk_downloads"
        download_dir.mkdir(parents=True, exist_ok=True)

        result = {}

        async with aiohttp.ClientSession() as _session:
            for name, url in urls.items():
                filepath = self._raw_dir / "bulk_downloads" / f"{Path(url).name}"
                filepath.parent.mkdir(parents=True, exist_ok=True)

                if filepath.exists() and not force:
                    logger.info(
                        "File already exists, skipping download",
                        extra={"file": str(filepath)},
                    )
                    result[name] = filepath
                    continue

                logger.info("Downloading", extra={"url": url, "file": str(filepath)})
                try:
                    async with self.client._request(url) as response:
                        if response.status == 200:
                            content = await response.read()
                            filepath.write_bytes(content)
                            logger.info(
                                "Downloaded",
                                extra={"file": str(filepath), "size": len(content)},
                            )
                            result[name] = filepath
                        else:
                            raise RuntimeError(
                                f"Failed to download {url}: {response.status}"
                            )
                except (aiohttp.ClientError, RuntimeError) as e:
                    logger.error("Download failed", extra={"url": url, "error": str(e)})
                    raise

        return result

    async def extract_zip(self, zip_path: Path, extract_to: Path) -> list[Path]:
        """Extract ZIP file and return list of extracted files."""
        extract_to.mkdir(parents=True, exist_ok=True)

        extracted_files = []
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_to)
            for member in zf.namelist():
                extracted_path = extract_to / member
                if extracted_path.is_file():
                    extracted_files.append(extracted_path)

        logger.info(
            "Extracted ZIP", extra={"zip": str(zip_path), "files": len(extracted_files)}
        )
        return extracted_files

    async def ingest_companyfacts(
        self, companyfacts_path: Path, checkpoint: BulkImportCheckpoint | None = None
    ) -> BulkImportStats:
        """Ingest companyfacts.json using streaming JSON parsing."""
        stats = BulkImportStats()

        # Load or create checkpoint
        if checkpoint is None:
            checkpoint = BulkImportCheckpoint(dataset="companyfacts")
            self._load_checkpoint("companyfacts", checkpoint)

        logger.info(
            "Starting companyfacts ingestion", extra={"file": str(companyfacts_path)}
        )

        # Parse JSON incrementally using ijson
        async with aiofiles.open(companyfacts_path, "rb") as f:
            content = await f.read()
            parser = ijson.parse(content)
            current_cik = None
            current_company_facts = None
            in_facts = False

            companies_to_process = []

            for prefix, event, value in parser:
                if prefix == "cik" and event == "string":
                    # Start of a new company
                    if current_cik is not None and current_company_facts is not None:
                        # Process the previous company
                        companies_to_process.append(
                            (current_cik, current_company_facts)
                        )

                    current_cik = value
                    current_company_facts = {
                        "cik": value,
                        "entityName": "",
                        "facts": {},
                    }
                    logger.debug("Processing company", extra={"cik": value})

                elif (
                    prefix == "entityName"
                    and event == "string"
                    and current_company_facts is not None
                ):
                    current_company_facts["entityName"] = value

                elif (
                    prefix == "facts"
                    and event == "map_key"
                    or prefix.endswith(".facts")
                    and event == "map_key"
                ):
                    in_facts = True
                    if current_company_facts is not None:
                        current_company_facts["facts"][value] = {}

                elif in_facts and prefix.endswith(".label") and event == "string":
                    # Skip label
                    pass

                elif prefix.endswith(".units") and event == "map_key":
                    # Skip unit key
                    pass

                elif prefix.endswith(".units") and event == "array" and in_facts:
                    # Start of values array
                    pass

                elif in_facts and prefix.count(".") == 3 and event == "map_key":
                    # Inside a unit, starting a new value object
                    pass

            # Process remaining company
            if current_cik is not None and current_company_facts is not None:
                companies_to_process.append((current_cik, current_company_facts))

            logger.info(f"Found {len(companies_to_process)} companies to process")

        # Process each company
        for cik, company_facts in companies_to_process:
            if (
                checkpoint
                and checkpoint.last_processed_cik
                and cik <= checkpoint.last_processed_cik
            ):
                logger.debug("Skipping already processed CIK", extra={"cik": cik})
                continue

            try:
                company_data = (
                    companies_to_process.pop(0)
                    if companies_to_process
                    else {"facts": {}, "entityName": ""}
                )
                await self._process_company_facts(
                    cik,
                    {
                        "facts": company_data[1]["facts"],
                        "entityName": company_data[1]["entityName"],
                    },
                    {},
                    self._get_provider_id(),
                    stats,
                )
            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                logger.error(
                    "Failed to process company", extra={"cik": cik, "error": str(e)}
                )

        return stats

    async def ingest_submissions(
        self, submissions_dir: Path, checkpoint: BulkImportCheckpoint | None = None
    ) -> BulkImportStats:
        """Ingest submissions JSON files."""

    async def ingest_company_tickers(self, tickers_path: Path) -> BulkImportStats:
        """Import company tickers reference data."""

    def _save_checkpoint(self, checkpoint: BulkImportCheckpoint):
        """Save checkpoint to disk."""

    def _load_checkpoint(self, dataset: str) -> BulkImportCheckpoint | None:
        """Load checkpoint from disk."""

    def _get_provider_id(self):
        """Get or create SEC provider ID."""

    async def seed_exchanges(self) -> int:
        """Seed exchanges table with SEC exchange mappings."""

    async def _process_company_facts(
        self,
        cik: str,
        company_facts: dict,
        filing_id_map: dict,
        provider_id,
        stats: BulkImportStats,
    ) -> None:
        """Process a single company's facts."""
        # Create SECCompanyFacts object
        sec_company_facts = SECCompanyFacts(
            cik=cik,
            entityName=company_facts.get("entityName", ""),
            facts=self._parse_company_facts_dict(company_facts.get("facts", {})),
            metadata={},
        )

        # Parse facts
        parsed_facts = self.parser.parse_company_facts(sec_company_facts)

        # Set provider_id on all facts
        for fact in parsed_facts:
            fact.provider_id = str(provider_id)

        # Import facts
        for fact in parsed_facts:
            stats.facts_processed += 1
            try:
                await self._import_financial_fact(cik, fact, stats)
            except (ValueError, TypeError, KeyError) as e:
                stats.errors.append(
                    {
                        "cik": cik,
                        "concept": fact.concept,
                        "namespace": fact.namespace,
                        "error": str(e),
                        "type": type(e).__name__,
                    }
                )
                stats.facts_validation_errors += 1
                logger.error(
                    "Failed to import fact",
                    extra={"cik": cik, "concept": fact.concept, "error": str(e)},
                )

    def _build_filing_id_map(
        self, company_id: str, provider_id: uuid.UUID
    ) -> dict[str, str]:
        """Build mapping from accession_number to internal filing_id."""
        mapping = {}
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT accession_number, id FROM filings
                   WHERE company_id = %s AND provider_id = %s""",
                (company_id, str(provider_id)),
            )
            for row in cur.fetchall():
                mapping[row["accession_number"]] = str(row["id"])
        return mapping

    async def _import_financial_fact(
        self, company_id: str, fact: ParsedFinancialFact, stats: BulkImportStats
    ) -> None:
        """Import a single financial fact with validation."""
        # Validate
        errors = validate_financial_fact(fact)
        if errors:
            stats.facts_validation_errors += 1
            raise ValueError(f"Validation failed: {', '.join(errors)}")

        # Check for existing fact (idempotency)
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT id FROM financial_facts
                   WHERE company_id = %s AND concept = %s
                   AND period_start IS NOT DISTINCT FROM %s
                   AND period_end = %s
                   AND filing_id IS NOT DISTINCT FROM %s
                   AND source_id = %s""",
                (
                    company_id,
                    fact.concept,
                    fact.period_start,
                    fact.period_end,
                    fact.filing_id,
                    fact.source_id,
                ),
            )
            if cur.fetchone():
                stats.facts_skipped += 1
                return

        # Insert fact
        result = self.facts.create(
            company_id=company_id,
            concept=fact.concept,
            value=fact.value,
            unit=fact.unit,
            period_start=str(fact.period_start) if fact.period_start else None,
            period_end=str(fact.period_end),
            fiscal_year=fact.fiscal_year,
            fiscal_period=fact.fiscal_period,
            provider_id=fact.provider_id,
            source_id=fact.source_id,
            filing_id=fact.filing_id,
            form=fact.form,
            filing_date=str(fact.filing_date) if fact.filing_date else None,
            namespace=fact.namespace,
            frame=fact.frame,
        )

        if result:
            stats.facts_inserted += 1
        else:
            stats.facts_skipped += 1

    def _parse_company_facts_dict(
        self, facts_dict: dict
    ) -> dict[str, dict[str, SECCompanyFact]]:
        """Parse the company facts dict into SECCompanyFact objects."""
        result = {}
        for namespace, concepts in facts_dict.items():
            namespace_dict = {}
            for concept_name, concept_data in concepts.items():
                values = []
                for unit_data in concept_data.get("units", {}).values():
                    for val_data in unit_data:
                        # Parse dates
                        period_start = None
                        period_end = None
                        if val_data.get("start"):
                            try:
                                period_start = date.fromisoformat(val_data["start"])
                            except ValueError:
                                pass
                        if val_data.get("end"):
                            try:
                                period_end = date.fromisoformat(val_data["end"])
                            except ValueError:
                                pass

                        # Determine if instant or duration
                        is_instant = period_start is None or period_start == period_end

                        values.append(
                            SECCompanyFactValue(
                                value=val_data.get("val", 0),
                                period_start=period_start,
                                period_end=period_end or datetime.now(UTC).date(),
                                fiscal_year=val_data.get("fy"),
                                fiscal_period=val_data.get("fp"),
                                form=val_data.get("form"),
                                filing_date=date.fromisoformat(val_data["filed"])
                                if val_data.get("filed")
                                else None,
                                accession_number=val_data.get("accn"),
                                frame=val_data.get("frame"),
                                is_instant=is_instant,
                                metadata={
                                    k: v
                                    for k, v in val_data.items()
                                    if k
                                    not in {
                                        "val",
                                        "start",
                                        "end",
                                        "fy",
                                        "fp",
                                        "form",
                                        "filed",
                                        "accn",
                                        "frame",
                                    }
                                },
                            )
                        )

                fact = SECCompanyFact(
                    concept=concept_name,
                    namespace=namespace,
                    label=concept_data.get("label"),
                    unit=concept_data.get("unit", ""),
                    values=values,
                )
                namespace_dict[concept_name] = fact
            result[namespace] = namespace_dict
        return result


async def create_bulk_ingester(
    database_url: str | None = None,
    user_agent: str | None = None,
    raw_dir: Path | None = None,
    checkpoint_dir: Path | None = None,
    batch_size: int = 100,
) -> tuple[SECBulkIngester, SECClient]:
    """Factory function to create SEC bulk ingester with dependencies."""
    import os

    from financial_database.providers.sec.client import SECClient

    url = database_url or os.environ.get(
        "DATABASE_URL", "postgresql://financial:test@localhost:5432/financial_database"
    )
    conn = psycopg.connect(url)
    client = SECClient(user_agent=user_agent, raw_dir=raw_dir)
    ingester = SECBulkIngester(
        conn, client, SECParser(), Path(raw_dir or "./data/raw/sec"), batch_size=100
    )
    return ingester, client
