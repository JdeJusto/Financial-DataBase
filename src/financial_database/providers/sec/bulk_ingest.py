"""SEC EDGAR bulk ingestion module for processing bulk data files."""

import hashlib
import json
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

# Note: SEC bulk file URLs may change. These are the official URLs as of 2024.
# If bulk downloads fail, files must be obtained manually from SEC EDGAR.
SEC_BULK_COMPANYFACTS_URL = "https://www.sec.gov/files/companyfacts.zip"
SEC_BULK_SUBMISSIONS_URL = "https://www.sec.gov/files/submissions.zip"
SEC_BULK_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"

# Alternative working URL for company tickers
SEC_COMPANY_TICKERS_JSON_URL = "https://www.sec.gov/files/company_tickers.json"


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
    provider: str = "SEC EDGAR"
    source_file: str = ""
    source_file_checksum: str = ""
    cik: str | None = None
    last_processed_cik: str | None = None
    companies_processed: int = 0
    facts_processed: int = 0
    filings_processed: int = 0
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "provider": self.provider,
            "source_file": self.source_file,
            "source_file_checksum": self.source_file_checksum,
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
            provider=data.get("provider", "SEC EDGAR"),
            source_file=data.get("source_file", ""),
            source_file_checksum=data.get("source_file_checksum", ""),
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

    def _compute_file_checksum(self, file_path: Path) -> str:
        """Compute SHA256 checksum of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _compute_dir_checksum(self, dir_path: Path) -> str:
        """Compute SHA256 checksum of all files in a directory (sorted by name)."""
        sha256 = hashlib.sha256()
        for file_path in sorted(dir_path.rglob("*")):
            if file_path.is_file():
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        sha256.update(chunk)
        return sha256.hexdigest()

    def _get_checkpoint_path(self, dataset: str) -> Path:
        """Get checkpoint file path for a dataset."""
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        return self.checkpoint_dir / f"{dataset}_checkpoint.json"

    def _save_checkpoint(self, checkpoint: BulkImportCheckpoint):
        """Save checkpoint to disk atomically."""
        checkpoint.updated_at = datetime.now(UTC)
        checkpoint_path = self._get_checkpoint_path(checkpoint.dataset)
        temp_path = checkpoint_path.with_suffix(".tmp")
        try:
            with open(temp_path, "w") as f:
                json.dump(checkpoint.to_dict(), f, indent=2)
            temp_path.replace(checkpoint_path)
            logger.debug("Checkpoint saved", extra={"path": str(checkpoint_path)})
        except OSError as e:
            logger.error("Failed to save checkpoint", extra={"error": str(e)})
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

    def _load_checkpoint(self, dataset: str) -> BulkImportCheckpoint | None:
        """Load checkpoint from disk."""
        checkpoint_path = self._get_checkpoint_path(dataset)
        if not checkpoint_path.exists():
            return None
        try:
            with open(checkpoint_path) as f:
                data = json.load(f)
            logger.debug("Checkpoint loaded", extra={"path": str(checkpoint_path)})
            return BulkImportCheckpoint.from_dict(data)
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Failed to load checkpoint", extra={"error": str(e)})
            return None

    def _get_provider_id(self):
        """Get or create SEC provider ID."""
        if self._provider_id is not None:
            return self._provider_id

        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM data_providers WHERE name = %s",
                (self.SEC_PROVIDER_NAME,),
            )
            row = cur.fetchone()
            if row:
                self._provider_id = uuid.UUID(str(row["id"]))
                return self._provider_id

            # Create provider
            cur.execute(
                """INSERT INTO data_providers (name, type, display_name, base_url, rate_limit_per_second, is_active)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (
                    self.SEC_PROVIDER_NAME,
                    self.SEC_PROVIDER_TYPE,
                    "SEC EDGAR",
                    "https://www.sec.gov",
                    10.0,
                    True,
                ),
            )
            self._provider_id = uuid.UUID(str(cur.fetchone()["id"]))
            self.conn.commit()
            logger.info(
                "Created SEC provider", extra={"provider_id": str(self._provider_id)}
            )
            return self._provider_id

    async def download_bulk_files(self, force: bool = False) -> dict[str, Path]:
        """Download SEC bulk data files."""
        urls = {
            "companyfacts": self.SEC_BULK_COMPANYFACTS_URL,
            "submissions": self.SEC_BULK_SUBMISSIONS_URL,
            "tickers": self.SEC_BULK_COMPANY_TICKERS_URL,
            "tickers_json": self.SEC_COMPANY_TICKERS_JSON_URL,
        }

        download_dir = self._raw_dir / "bulk_downloads"
        download_dir.mkdir(parents=True, exist_ok=True)

        result = {}

        # Ensure client session is initialized
        await self.client._ensure_session()

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
                async with self.client._session.get(url) as response:
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
        self,
        companyfacts_path: Path,
        checkpoint: BulkImportCheckpoint | None = None,
        limit: int | None = None,
    ) -> BulkImportStats:
        """Ingest companyfacts.json using streaming JSON parsing with checkpointing."""
        stats = BulkImportStats()

        # Compute source file checksum
        source_checksum = self._compute_file_checksum(companyfacts_path)

        # Load or create checkpoint
        if checkpoint is None:
            checkpoint = BulkImportCheckpoint(
                dataset="companyfacts",
                source_file=str(companyfacts_path),
                source_file_checksum=source_checksum,
            )
            loaded_checkpoint = self._load_checkpoint("companyfacts")
            if loaded_checkpoint:
                # Validate checkpoint matches current source file
                if loaded_checkpoint.source_file_checksum != source_checksum:
                    logger.warning(
                        "Checkpoint source file checksum mismatch, starting fresh",
                        extra={
                            "checkpoint_checksum": loaded_checkpoint.source_file_checksum,
                            "current_checksum": source_checksum,
                        },
                    )
                else:
                    checkpoint = loaded_checkpoint
                    logger.info(
                        "Resuming from checkpoint",
                        extra={
                            "last_processed_cik": checkpoint.last_processed_cik,
                            "companies_processed": checkpoint.companies_processed,
                        },
                    )

        # Update checkpoint with current file info
        checkpoint.source_file = str(companyfacts_path)
        checkpoint.source_file_checksum = source_checksum
        checkpoint.provider = self.SEC_PROVIDER_NAME

        logger.info(
            "Starting companyfacts ingestion",
            extra={
                "file": str(companyfacts_path),
                "checksum": source_checksum[:16],
                "resume_from_cik": checkpoint.last_processed_cik,
            },
        )

        # Parse JSON incrementally using ijson - collect all companies first
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
                        companies_to_process.append(
                            (current_cik, current_company_facts)
                        )

                    current_cik = value
                    current_company_facts = {
                        "cik": value,
                        "entityName": "",
                        "facts": {},
                    }

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

        # Apply limit if specified
        if limit is not None and limit > 0:
            companies_to_process = companies_to_process[:limit]
            logger.info(f"Limited to first {limit} companies")

        provider_id = self._get_provider_id()

        # Process each company
        processed_count = 0
        for cik, company_facts in companies_to_process:
            # Skip if already processed (resume from checkpoint)
            if checkpoint.last_processed_cik and cik <= checkpoint.last_processed_cik:
                logger.debug("Skipping already processed CIK", extra={"cik": cik})
                continue

            # Check if company exists in database (idempotency)
            company_id = None
            with self.conn.cursor() as cur:
                cur.execute(
                    """SELECT c.id FROM companies c
                       JOIN company_identifiers ci ON c.id = ci.company_id
                       WHERE ci.identifier_type = 'CIK' AND ci.identifier_value = %s
                       AND ci.provider_id = (SELECT id FROM data_providers WHERE name = %s)""",
                    (cik, self.SEC_PROVIDER_NAME),
                )
                row = cur.fetchone()
                if row:
                    company_id = str(row["id"])

            if company_id is None:
                # Create company record if it doesn't exist
                from financial_database.db.repositories import CompanyRepository

                company_repo = CompanyRepository(self.conn)
                try:
                    company = company_repo.create(
                        legal_name=company_facts.get("entityName", ""),
                    )
                    if company:
                        company_id = str(company["id"])
                        stats.companies_inserted += 1
                        # Add CIK identifier
                        self.identifiers.create(
                            company_id=company_id,
                            identifier_type="CIK",
                            identifier_value=cik,
                            provider_id=provider_id,
                        )
                        stats.identifiers_inserted += 1
                except (OSError, psycopg.Error) as e:
                    logger.error(
                        "Failed to create company", extra={"cik": cik, "error": str(e)}
                    )
                    stats.errors.append(
                        {"cik": cik, "error": str(e), "stage": "company_creation"}
                    )
                    continue
            else:
                stats.companies_inserted += 0  # Already counted as processed
                stats.companies_updated += 1

            stats.companies_processed += 1
            processed_count += 1

            # Process this company's facts
            try:
                await self._process_company_facts(
                    cik,
                    {
                        "facts": company_facts.get("facts", {}),
                        "entityName": company_facts.get("entityName", ""),
                    },
                    {},
                    provider_id,
                    stats,
                )

                # Update checkpoint after successful company processing
                checkpoint.last_processed_cik = cik
                checkpoint.companies_processed = stats.companies_processed
                checkpoint.facts_processed = stats.facts_processed
                self._save_checkpoint(checkpoint)

            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                logger.error(
                    "Failed to process company", extra={"cik": cik, "error": str(e)}
                )
                stats.errors.append(
                    {"cik": cik, "error": str(e), "stage": "fact_processing"}
                )
                # Still advance checkpoint past failed company to avoid infinite retry
                checkpoint.last_processed_cik = cik
                checkpoint.companies_processed = stats.companies_processed
                self._save_checkpoint(checkpoint)

        # Final checkpoint save
        self._save_checkpoint(checkpoint)

        logger.info(
            "Companyfacts ingestion complete",
            extra={
                "companies_processed": stats.companies_processed,
                "facts_inserted": stats.facts_inserted,
                "facts_skipped": stats.facts_skipped,
                "errors": len(stats.errors),
            },
        )

        return stats

    async def ingest_company_tickers(self, tickers_path: Path) -> BulkImportStats:
        """Import company tickers reference data from SEC company_tickers_exchange.json.

        The file structure is:
        {
          "data": [
            ["0000320193", "Apple Inc.", "AAPL", "NASDAQ", "3571", "Electronic Computers", "..."],
            ...
          ]
        }
        """
        stats = BulkImportStats()
        provider_id = self._get_provider_id()

        logger.info(
            "Starting company tickers ingestion", extra={"file": str(tickers_path)}
        )

        # Stream parse the JSON array
        async with aiofiles.open(tickers_path, "rb") as f:
            content = await f.read()
            parser = ijson.parse(content)

            in_data = False
            in_item = False
            current_item = []
            item_index = 0

            for prefix, event, value in parser:
                if prefix == "data" and event == "start_array":
                    in_data = True
                elif prefix == "data" and event == "end_array":
                    in_data = False
                elif in_data and event == "start_array":
                    in_item = True
                    current_item = []
                elif in_data and event == "end_array":
                    in_item = False
                    # Process the item
                    if len(current_item) >= 3:
                        await self._process_ticker_item(
                            current_item, provider_id, stats
                        )
                    item_index += 1
                    if item_index % 1000 == 0:
                        logger.debug(f"Processed {item_index} ticker items")
                elif in_data and in_item and event in ("string", "number", "null"):
                    current_item.append(value if value is not None else "")

        logger.info(
            "Company tickers ingestion complete",
            extra={
                "companies_inserted": stats.companies_inserted,
                "companies_updated": stats.companies_updated,
                "identifiers_inserted": stats.identifiers_inserted,
                "listings_inserted": stats.listings_inserted,
                "exchanges_inserted": stats.exchanges_inserted,
                "errors": len(stats.errors),
            },
        )
        return stats

    async def _process_ticker_item(
        self, item: list, provider_id, stats: BulkImportStats
    ) -> None:
        """Process a single ticker item from company_tickers_exchange.json."""
        try:
            cik = str(item[0]).zfill(10)
            name = item[1] if len(item) > 1 else ""
            ticker = item[2] if len(item) > 2 and item[2] else None
            exchange = item[3] if len(item) > 3 and item[3] else None
            _ = item[4] if len(item) > 4 and item[4] else None  # sic - not used yet

            # Upsert company by CIK
            company_id = None
            with self.conn.cursor() as cur:
                cur.execute(
                    """SELECT c.id FROM companies c
                       JOIN company_identifiers ci ON c.id = ci.company_id
                       WHERE ci.identifier_type = 'CIK' AND ci.identifier_value = %s
                       AND ci.provider_id = (SELECT id FROM data_providers WHERE name = %s)""",
                    (cik, self.SEC_PROVIDER_NAME),
                )
                row = cur.fetchone()
                if row:
                    company_id = str(row["id"])

            if company_id is None:
                # Create company
                from financial_database.db.repositories import CompanyRepository

                company_repo = CompanyRepository(self.conn)
                company = company_repo.create(legal_name=name.strip())
                if company:
                    company_id = str(company["id"])
                    stats.companies_inserted += 1
                    # Add CIK identifier
                    self.identifiers.create(
                        company_id=company_id,
                        identifier_type="CIK",
                        identifier_value=cik,
                        provider_id=provider_id,
                    )
                    stats.identifiers_inserted += 1
            else:
                stats.companies_updated += 1

            # Add ticker as identifier if available
            if ticker:
                self.identifiers.create(
                    company_id=company_id,
                    identifier_type="TICKER",
                    identifier_value=ticker.upper(),
                    provider_id=provider_id,
                )
                stats.identifiers_inserted += 1

            # Create listing if ticker and exchange available
            if ticker and exchange:
                mapping = self.parser._get_exchange_mapping(exchange)
                if mapping:
                    # Check if listing already exists
                    with self.conn.cursor() as cur:
                        cur.execute(
                            """SELECT id FROM company_listings
                               WHERE company_id = %s AND exchange_id = (
                                   SELECT id FROM exchanges WHERE code = %s
                               ) AND ticker = %s""",
                            (company_id, mapping.internal_code, ticker.upper()),
                        )
                        existing = cur.fetchone()

                    if not existing:
                        self.listings.create(
                            company_id=company_id,
                            exchange_code=mapping.internal_code,
                            ticker=ticker.upper(),
                            mic=mapping.mic,
                            country=mapping.country,
                            timezone=mapping.timezone,
                            currency=mapping.currency,
                            is_primary=True,
                        )
                        stats.listings_inserted += 1
                        self.conn.commit()
                else:
                    logger.warning(
                        "Unknown SEC exchange, listing not created",
                        extra={"cik": cik, "exchange": exchange},
                    )

        except (ValueError, TypeError, KeyError, RuntimeError) as e:
            logger.error(
                "Failed to process ticker item", extra={"item": item, "error": str(e)}
            )
            stats.errors.append({"item": item, "error": str(e)})

    async def ingest_submissions(
        self, submissions_dir: Path, checkpoint: BulkImportCheckpoint | None = None
    ) -> BulkImportStats:
        """Ingest submissions JSON files from extracted submissions.zip.

        The submissions.zip contains individual JSON files named like:
        - CIK0000320193.json
        - CIK0000789019.json
        etc.

        Each file has the same structure as the single-company submissions API response.
        """
        stats = BulkImportStats()
        provider_id = self._get_provider_id()

        # Load or create checkpoint
        if checkpoint is None:
            checkpoint = BulkImportCheckpoint(dataset="submissions")
            loaded = self._load_checkpoint("submissions")
            if loaded:
                checkpoint = loaded

        # Compute source file checksum
        source_checksum = self._compute_dir_checksum(submissions_dir)

        logger.info(
            "Starting submissions ingestion",
            extra={
                "directory": str(submissions_dir),
                "checksum": source_checksum[:16],
                "resume_from_cik": checkpoint.last_processed_cik,
            },
        )

        # Update checkpoint with current file info
        checkpoint.source_file = str(submissions_dir)
        checkpoint.source_file_checksum = source_checksum
        checkpoint.provider = self.SEC_PROVIDER_NAME

        # Get all JSON files in the directory
        json_files = sorted(submissions_dir.glob("*.json"))
        logger.info(f"Found {len(json_files)} submission files to process")

        # Process each file
        for json_file in json_files:
            # Extract CIK from filename (CIK##########.json)
            filename = json_file.stem
            if not filename.startswith("CIK"):
                continue
            cik = filename[3:].zfill(10)

            # Skip if already processed (resume from checkpoint)
            if checkpoint.last_processed_cik and cik <= checkpoint.last_processed_cik:
                logger.debug("Skipping already processed CIK", extra={"cik": cik})
                continue

            try:
                await self._process_submissions_file(json_file, cik, provider_id, stats)

                # Update checkpoint after successful processing
                checkpoint.last_processed_cik = cik
                checkpoint.companies_processed = stats.companies_processed
                checkpoint.filings_processed = stats.filings_processed
                self._save_checkpoint(checkpoint)

            except (
                ValueError,
                TypeError,
                KeyError,
                RuntimeError,
                json.JSONDecodeError,
            ) as e:
                logger.error(
                    "Failed to process submissions file",
                    extra={"cik": cik, "file": str(json_file), "error": str(e)},
                )
                stats.errors.append(
                    {"cik": cik, "file": str(json_file), "error": str(e)}
                )
                # Still advance checkpoint to avoid infinite retry
                checkpoint.last_processed_cik = cik
                checkpoint.companies_processed = stats.companies_processed
                self._save_checkpoint(checkpoint)

        # Final checkpoint save
        self._save_checkpoint(checkpoint)

        logger.info(
            "Submissions ingestion complete",
            extra={
                "companies_processed": stats.companies_processed,
                "filings_processed": stats.filings_processed,
                "filings_inserted": stats.filings_inserted,
                "filings_skipped": stats.filings_skipped,
                "errors": len(stats.errors),
            },
        )
        return stats

    async def _process_submissions_file(
        self, json_file: Path, cik: str, provider_id, stats: BulkImportStats
    ) -> None:
        """Process a single company's submissions JSON file."""
        import json

        # Read and parse the JSON file
        async with aiofiles.open(json_file, "r") as f:
            content = await f.read()
            data = json.loads(content)

        # Get or create company
        company_id = None
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT c.id FROM companies c
                   JOIN company_identifiers ci ON c.id = ci.company_id
                   WHERE ci.identifier_type = 'CIK' AND ci.identifier_value = %s
                   AND ci.provider_id = (SELECT id FROM data_providers WHERE name = %s)""",
                (cik, self.SEC_PROVIDER_NAME),
            )
            row = cur.fetchone()
            if row:
                company_id = str(row["id"])

        if company_id is None:
            # Create company if it doesn't exist
            from financial_database.db.repositories import CompanyRepository

            company_repo = CompanyRepository(self.conn)
            entity_name = data.get("name", "")
            company = company_repo.create(legal_name=entity_name.strip())
            if company:
                company_id = str(company["id"])
                stats.companies_inserted += 1
                self.identifiers.create(
                    company_id=company_id,
                    identifier_type="CIK",
                    identifier_value=cik,
                    provider_id=provider_id,
                )
                stats.identifiers_inserted += 1
        else:
            stats.companies_updated += 1

        stats.companies_processed += 1

        # Parse filings from the submissions data
        recent = data.get("filings", {}).get("recent", {})
        if not recent:
            return

        count = len(recent.get("accessionNumber", []))
        for i in range(count):
            stats.filings_processed += 1

            accession = recent.get("accessionNumber", [None] * count)[i]
            form = recent.get("form", [None] * count)[i]
            filing_date_str = recent.get("filingDate", [None] * count)[i]
            period_end_str = recent.get("reportDate", [None] * count)[i]
            fiscal_year = recent.get("fy", [None] * count)[i]
            fiscal_period = recent.get("fp", [None] * count)[i]
            primary_doc = recent.get("primaryDocument", [None] * count)[i]
            primary_doc_desc = recent.get("primaryDocDescription", [None] * count)[i]

            if not accession or not form:
                continue

            # Normalize accession number (remove dashes)
            normalized_accession = accession.replace("-", "")

            # Parse dates
            filing_date = None
            if filing_date_str:
                try:
                    filing_date = date.fromisoformat(filing_date_str)
                except ValueError:
                    pass

            period_end = None
            if period_end_str and period_end_str != "":
                try:
                    period_end = date.fromisoformat(period_end_str)
                except ValueError:
                    pass

            # Determine if amended
            is_amended = form.endswith("/A")

            # Check for existing filing (idempotency)
            with self.conn.cursor() as cur:
                cur.execute(
                    """SELECT id FROM filings
                       WHERE company_id = %s AND accession_number = %s AND provider_id = %s""",
                    (company_id, normalized_accession, str(provider_id)),
                )
                existing = cur.fetchone()
                if existing:
                    stats.filings_skipped += 1
                    continue

            # Insert filing
            from financial_database.db.repositories import FilingRepository

            filing_repo = FilingRepository(self.conn)
            result = filing_repo.create(
                company_id=company_id,
                provider_id=provider_id,
                accession_number=normalized_accession,
                form=form,
                filing_date=filing_date,
                period_end=period_end,
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period or "FY",
                is_amended=is_amended,
                primary_document=primary_doc,
                primary_doc_description=primary_doc_desc,
                source_id=normalized_accession,
            )

            if result:
                stats.filings_inserted += 1
            else:
                stats.filings_skipped += 1

    async def seed_exchanges(self) -> int:
        """Seed exchanges table with SEC exchange mappings."""
        from financial_database.providers.sec import get_exchange_mappings

        inserted = 0
        for mapping in get_exchange_mappings():
            result = self.exchanges.create(
                code=mapping.internal_code,
                name=mapping.internal_name,
                country=mapping.country,
                timezone=mapping.timezone,
                currency=mapping.currency,
            )
            if result:
                inserted += 1
        self.conn.commit()
        logger.info(f"Seeded {inserted} exchanges")
        return inserted

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
