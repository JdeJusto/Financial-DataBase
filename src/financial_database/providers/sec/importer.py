"""SEC EDGAR importer - orchestrates the full ingestion pipeline."""

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
    SECNotFoundError,
    SECRateLimitError,
    SECServerError,
)
from financial_database.providers.sec.models import (
    SECCompany,
    get_exchange_mappings,
    normalize_cik,
)
from financial_database.providers.sec.parser import (
    ParsedCompany,
    ParsedFiling,
    ParsedFinancialFact,
    SECParser,
    validate_financial_fact,
)

logger = logging.getLogger(__name__)

SEC_PROVIDER_NAME = "SEC EDGAR"
SEC_PROVIDER_TYPE = "sec"


@dataclass
class ImportStats:
    """Statistics for an import operation."""

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

    def __post_init__(self) -> None:
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


class SECImporter:
    """SEC EDGAR data importer with full provenance tracking."""

    def __init__(
        self,
        conn: psycopg.Connection,
        client: SECClient,
        parser: SECParser | None = None,
    ):
        self.conn = conn
        self.client = client
        self.parser = parser or SECParser()
        self._raw_dir = client._raw_dir

        # Repositories
        self.companies = CompanyRepository(conn)
        self.identifiers = CompanyIdentifierRepository(conn)
        self.listings = CompanyListingRepository(conn)
        self.exchanges = ExchangeRepository(conn)
        self.filings = FilingRepository(conn)
        self.facts = FinancialFactRepository(conn)
        self.raw_docs = RawDocumentRepository(conn)
        self.import_runs = ImportRunRepository(conn)

        # Provider ID (cached)
        self._provider_id: uuid.UUID | None = None

    def _get_provider_id(self) -> uuid.UUID:
        """Get or create SEC provider ID."""
        if self._provider_id is None:
            self._provider_id = self._ensure_provider()
        return self._provider_id

    def _ensure_provider(self) -> uuid.UUID:
        """Ensure SEC provider exists in data_providers table."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM data_providers WHERE name = %s", (SEC_PROVIDER_NAME,)
            )
            row = cur.fetchone()
            if row:
                return uuid.UUID(str(row["id"]))

            # Create provider
            cur.execute(
                """INSERT INTO data_providers (name, type, display_name, base_url, rate_limit_per_second, is_active)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (
                    SEC_PROVIDER_NAME,
                    SEC_PROVIDER_TYPE,
                    "SEC EDGAR",
                    "https://www.sec.gov",
                    10.0,
                    True,
                ),
            )
            provider_id = uuid.UUID(str(cur.fetchone()["id"]))
            self.conn.commit()
            logger.info("Created SEC provider", extra={"provider_id": str(provider_id)})
            return provider_id

    async def seed_exchanges(self) -> int:
        """Seed exchanges table with SEC exchange mappings."""
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
        if inserted:
            self.conn.commit()
            logger.info("Seeded exchanges", extra={"inserted": inserted})
        return inserted

    async def import_company_universe(
        self, stats: ImportStats | None = None
    ) -> ImportStats:
        """Import SEC company universe (tickers, CIKs, exchanges)."""
        stats = stats or ImportStats()
        provider_id = self._get_provider_id()

        logger.info("Starting SEC company universe import")
        companies = await self.client.get_company_tickers()

        # Create raw_document record for company tickers reference
        raw_doc_path = self._raw_dir / "reference" / "company_tickers_exchange.json"
        if raw_doc_path.exists():
            import hashlib

            checksum = hashlib.sha256(raw_doc_path.read_bytes()).hexdigest()
            self.raw_docs.create(
                provider_id=str(provider_id),
                source_identifier="reference:company_tickers_exchange",
                storage_path=str(raw_doc_path),
                checksum=checksum,
                content_type="application/json",
                metadata={},
            )
            stats.raw_documents_created += 1

        for sec_company in companies:
            stats.companies_processed += 1
            try:
                self._import_single_company(sec_company, provider_id, stats)
            except Exception as e:  # noqa: BLE001 - catch all to continue with other companies
                error_info = {
                    "cik": sec_company.cik,
                    "name": sec_company.name,
                    "error": str(e),
                    "type": type(e).__name__,
                }
                stats.errors.append(error_info)
                logger.error("Failed to import company", extra=error_info)

        self.conn.commit()
        logger.info("Company universe import complete", extra=stats.to_dict())
        return stats

    def _import_single_company(
        self,
        sec_company: SECCompany,
        provider_id: uuid.UUID,
        stats: ImportStats,
    ) -> None:
        """Import a single company with identifiers and listings."""
        parsed = self.parser.parse_company(sec_company)

        # Upsert company by CIK (check if exists via identifier)
        company_id = self._upsert_company_by_cik(parsed, stats)

        # Upsert identifiers
        for id_type, id_value in parsed.identifiers.items():
            result = self.identifiers.create(
                company_id=company_id,
                identifier_type=id_type,
                identifier_value=id_value,
                provider_id=str(provider_id),
                is_primary=(id_type == "CIK"),
            )
            if result:
                stats.identifiers_inserted += 1

        # Upsert listings
        for listing in parsed.listings:
            # Ensure exchange exists
            exchange = self.exchanges.get_by_code(listing.exchange_code)
            if not exchange:
                exchange_result = self.exchanges.create(
                    code=listing.exchange_code,
                    name=listing.exchange_name,
                    country=listing.country,
                    timezone=listing.timezone,
                    currency=listing.currency,
                )
                if exchange_result:
                    stats.exchanges_inserted += 1
                exchange = exchange_result

            if exchange:
                # Check for existing active listing to avoid duplicates
                # Normalize empty share_class to None for consistent comparison
                share_class_norm = listing.share_class if listing.share_class else None
                existing_listing_id = None
                with self.conn.cursor() as cur:
                    cur.execute(
                        """SELECT id FROM company_listings
                           WHERE company_id = %s AND exchange_id = %s AND ticker = %s
                           AND share_class IS NOT DISTINCT FROM %s
                           AND delisting_date IS NULL""",
                        (
                            company_id,
                            str(exchange["id"]),
                            listing.ticker,
                            share_class_norm,
                        ),
                    )
                    row = cur.fetchone()
                    if row:
                        existing_listing_id = row["id"]

                if existing_listing_id:
                    stats.listings_updated += 1
                else:
                    result = self.listings.create(
                        company_id=company_id,
                        exchange_id=str(exchange["id"]),
                        ticker=listing.ticker,
                        share_class=share_class_norm,
                        listing_date=str(listing.listing_date)
                        if listing.listing_date
                        else None,
                        delisting_date=str(listing.delisting_date)
                        if listing.delisting_date
                        else None,
                        is_primary=listing.is_primary,
                    )
                    if result:
                        stats.listings_inserted += 1

    def _upsert_company_by_cik(self, parsed: ParsedCompany, stats: ImportStats) -> str:
        """Upsert company by CIK identifier."""
        # Check if company exists via CIK identifier
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT c.id FROM companies c
                   JOIN company_identifiers ci ON c.id = ci.company_id
                   WHERE ci.identifier_type = 'CIK' AND ci.identifier_value = %s""",
                (parsed.cik,),
            )
            row = cur.fetchone()

        if row:
            company_id = str(row["id"])
            # Update company if needed
            self.companies.update(
                company_id=company_id,
                legal_name=parsed.legal_name,
                country=parsed.country,
                sector=parsed.sector,
                industry=parsed.industry,
                currency=parsed.currency,
                website=parsed.website,
            )
            stats.companies_updated += 1
            return company_id

        # Create new company
        result = self.companies.create(
            legal_name=parsed.legal_name,
            country=parsed.country,
            sector=parsed.sector,
            industry=parsed.industry,
            currency=parsed.currency,
            website=parsed.website,
        )
        if result:
            stats.companies_inserted += 1
            return str(result["id"])

        raise RuntimeError(f"Failed to create company: {parsed.legal_name}")

    async def import_submissions(
        self,
        cik: str,
        stats: ImportStats | None = None,
    ) -> ImportStats:
        """Import submissions (filings) for a specific CIK."""
        stats = stats or ImportStats()
        provider_id = self._get_provider_id()

        logger.info("Starting SEC submissions import", extra={"cik": cik})

        try:
            submissions = await self.client.get_submissions(cik)
        except SECNotFoundError:
            logger.warning("Company not found in SEC", extra={"cik": cik})
            stats.errors.append({"cik": cik, "error": "Not found in SEC"})
            return stats
        except (SECRateLimitError, SECServerError) as e:
            logger.error("SEC API error", extra={"cik": cik, "error": str(e)})
            stats.errors.append({"cik": cik, "error": str(e), "type": type(e).__name__})
            return stats

        # Get company_id
        company_id = self._get_company_id_by_cik(cik)
        if not company_id:
            logger.warning(
                "Company not in database, skipping submissions", extra={"cik": cik}
            )
            stats.errors.append({"cik": cik, "error": "Company not in local database"})
            return stats

        # Create raw_document record for submissions
        raw_doc_path = self._raw_dir / "submissions" / f"{cik.zfill(10)}.json"
        if raw_doc_path.exists():
            import hashlib

            checksum = hashlib.sha256(raw_doc_path.read_bytes()).hexdigest()
            self.raw_docs.create(
                provider_id=str(provider_id),
                source_identifier=f"submissions:{cik.zfill(10)}",
                storage_path=str(raw_doc_path),
                checksum=checksum,
                content_type="application/json",
                metadata={},
            )
            stats.raw_documents_created += 1

        # Parse and import filings
        parsed_filings = self.parser.parse_filings(submissions)

        for filing in parsed_filings:
            stats.filings_processed += 1
            try:
                self._import_filing(company_id, filing, provider_id, stats)
            except Exception as e:  # noqa: BLE001 - catch all to continue with other filings
                error_info = {
                    "cik": cik,
                    "accession": filing.accession_number,
                    "error": str(e),
                    "type": type(e).__name__,
                }
                stats.errors.append(error_info)
                logger.error("Failed to import filing", extra=error_info)

        self.conn.commit()
        logger.info(
            "Submissions import complete", extra={"cik": cik, **stats.to_dict()}
        )
        return stats

    def _get_company_id_by_cik(self, cik: str) -> str | None:
        """Get internal company_id by CIK."""
        normalized = normalize_cik(cik)
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT c.id FROM companies c
                   JOIN company_identifiers ci ON c.id = ci.company_id
                   WHERE ci.identifier_type = 'CIK' AND ci.identifier_value = %s""",
                (normalized,),
            )
            row = cur.fetchone()
            return str(row["id"]) if row else None

    def _import_filing(
        self,
        company_id: str,
        filing: ParsedFiling,
        provider_id: uuid.UUID,
        stats: ImportStats,
    ) -> str | None:
        """Import a single filing."""
        # Check if filing already exists
        existing = self.filings.get_by_accession(
            str(provider_id), filing.accession_number
        )
        if existing:
            stats.filings_skipped += 1
            return str(existing["id"])

        # Get raw_document_id if available
        raw_doc_id = None
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT id FROM raw_documents
                   WHERE provider_id = %s AND source_identifier = %s""",
                (str(provider_id), filing.accession_number),
            )
            row = cur.fetchone()
            if row:
                raw_doc_id = str(row["id"])

        result = self.filings.create(
            company_id=company_id,
            provider_id=str(provider_id),
            form=filing.form,
            accession_number=filing.accession_number,
            filing_date=str(filing.filing_date),
            period_start=str(filing.period_start) if filing.period_start else None,
            period_end=str(filing.period_end),
            fiscal_year=filing.fiscal_year,
            fiscal_period=filing.fiscal_period,
            filing_url=filing.filing_url,
            raw_document_id=raw_doc_id,
            is_amended=filing.is_amended,
        )

        if result:
            stats.filings_inserted += 1
            return str(result["id"])
        else:
            stats.filings_skipped += 1
            return None

    async def import_company_facts(
        self,
        cik: str,
        stats: ImportStats | None = None,
    ) -> ImportStats:
        """Import CompanyFacts (XBRL financial facts) for a specific CIK."""
        stats = stats or ImportStats()
        provider_id = self._get_provider_id()

        logger.info("Starting SEC CompanyFacts import", extra={"cik": cik})

        try:
            company_facts = await self.client.get_company_facts(cik)
        except SECNotFoundError:
            logger.warning("CompanyFacts not found", extra={"cik": cik})
            stats.errors.append({"cik": cik, "error": "CompanyFacts not found"})
            return stats
        except (SECRateLimitError, SECServerError) as e:
            logger.error("SEC API error", extra={"cik": cik, "error": str(e)})
            stats.errors.append({"cik": cik, "error": str(e), "type": type(e).__name__})
            return stats

        # Get company_id
        company_id = self._get_company_id_by_cik(cik)
        if not company_id:
            logger.warning(
                "Company not in database, skipping facts", extra={"cik": cik}
            )
            stats.errors.append({"cik": cik, "error": "Company not in local database"})
            return stats

        # Create raw_document record for companyfacts
        raw_doc_path = self._raw_dir / "companyfacts" / f"{cik.zfill(10)}.json"
        if raw_doc_path.exists():
            import hashlib

            try:
                file_bytes = raw_doc_path.read_bytes()
                checksum = hashlib.sha256(file_bytes).hexdigest()
            except OSError:
                # Fallback: read as text and encode
                file_text = raw_doc_path.read_text(encoding="utf-8")
                if isinstance(file_text, str):
                    checksum = hashlib.sha256(file_text.encode("utf-8")).hexdigest()
                else:
                    checksum = hashlib.sha256(
                        str(file_text).encode("utf-8")
                    ).hexdigest()
            self.raw_docs.create(
                provider_id=str(provider_id),
                source_identifier=f"companyfacts:{cik.zfill(10)}",
                storage_path=str(raw_doc_path),
                checksum=checksum,
                content_type="application/json",
                metadata={},
            )
            stats.raw_documents_created += 1

        # Build filing_id map for this company
        filing_id_map = self._build_filing_id_map(company_id, provider_id)

        # Parse facts
        parsed_facts = self.parser.parse_company_facts(company_facts, filing_id_map)

        # Set provider_id on all facts
        for fact in parsed_facts:
            fact.provider_id = str(provider_id)

        # Import facts
        for fact in parsed_facts:
            stats.facts_processed += 1
            try:
                self._import_financial_fact(company_id, fact, stats)
            except Exception as e:  # noqa: BLE001 - catch all to continue with other facts
                error_info = {
                    "cik": cik,
                    "concept": fact.concept,
                    "namespace": fact.namespace,
                    "error": str(e),
                    "type": type(e).__name__,
                }
                stats.errors.append(error_info)
                stats.facts_validation_errors += 1
                logger.error("Failed to import fact", extra=error_info)

        self.conn.commit()
        logger.info(
            "CompanyFacts import complete", extra={"cik": cik, **stats.to_dict()}
        )
        return stats

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
                if row is not None:
                    mapping[row["accession_number"]] = str(row["id"])
        return mapping

    def _import_financial_fact(
        self,
        company_id: str,
        fact: ParsedFinancialFact,
        stats: ImportStats,
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

    async def sync_company(
        self,
        cik: str,
        include_facts: bool = True,
        include_filings: bool = True,
        stats: ImportStats | None = None,
    ) -> ImportStats:
        """Full sync for a single company: universe + submissions + companyfacts."""
        if stats is None:
            stats = ImportStats()

        # Ensure provider and exchanges
        self._get_provider_id()
        await self.seed_exchanges()

        # Import company universe (this specific company)
        # We need to fetch the company from the universe first
        companies = await self.client.get_company_tickers()
        target_company = next(
            (c for c in companies if normalize_cik(c.cik) == normalize_cik(cik)), None
        )
        if target_company:
            self._import_single_company(target_company, self._get_provider_id(), stats)
        else:
            logger.warning("Company not in SEC universe", extra={"cik": cik})

        if include_filings:
            await self.import_submissions(cik, stats)

        if include_facts:
            await self.import_company_facts(cik, stats)

        self.conn.commit()
        return stats

    async def run_import_pipeline(
        self,
        pipeline_name: str,
        cik: str | None = None,
    ) -> ImportStats:
        """Run a complete import pipeline with import_run tracking."""
        provider_id = self._get_provider_id()
        run = self.import_runs.create(str(provider_id), pipeline_name, "running")
        run_id = str(run["id"])
        start_time = time.time()

        stats = ImportStats()

        try:
            if pipeline_name == "sec_universe":
                await self.seed_exchanges()
                await self.import_company_universe(stats)
            elif pipeline_name == "sec_submissions":
                if not cik:
                    raise ValueError("CIK required for submissions pipeline")
                await self.import_submissions(cik, stats)
            elif pipeline_name == "sec_companyfacts":
                if not cik:
                    raise ValueError("CIK required for companyfacts pipeline")
                await self.import_company_facts(cik, stats)
            elif pipeline_name == "sec_sync":
                if not cik:
                    raise ValueError("CIK required for sync pipeline")
                await self.sync_company(cik, stats=stats)
            else:
                raise ValueError(f"Unknown pipeline: {pipeline_name}")

            duration = int(time.time() - start_time)
            self.import_runs.update(
                run_id,
                status="success",
                records_processed=stats.companies_processed
                + stats.filings_processed
                + stats.facts_processed,
                records_inserted=stats.companies_inserted
                + stats.filings_inserted
                + stats.facts_inserted,
                records_updated=stats.companies_updated + stats.listings_updated,
                records_skipped=stats.filings_skipped + stats.facts_skipped,
                finished_at=datetime.now(UTC),
                duration_seconds=duration,
            )

        except Exception as e:
            duration = int(time.time() - start_time)
            self.import_runs.update(
                run_id,
                status="failed",
                records_processed=stats.companies_processed
                + stats.filings_processed
                + stats.facts_processed,
                records_inserted=stats.companies_inserted
                + stats.filings_inserted
                + stats.facts_inserted,
                records_updated=stats.companies_updated + stats.listings_updated,
                records_skipped=stats.filings_skipped + stats.facts_skipped,
                errors={"error": str(e), "type": type(e).__name__},
                finished_at=datetime.now(UTC),
                duration_seconds=duration,
            )
            stats.errors.append(
                {"import_run_id": run_id, "status": "failed", "error": str(e)}
            )
            raise

        finally:
            self.conn.commit()

        return stats


def create_sec_importer(
    database_url: str | None = None,
    user_agent: str | None = None,
    raw_dir: Path | None = None,
) -> tuple[SECImporter, SECClient]:
    """Factory function to create SEC importer with dependencies."""
    import os

    url = database_url or os.environ.get(
        "DATABASE_URL", "postgresql://financial:test@localhost:5432/financial_database"
    )
    conn = psycopg.connect(url)
    client = SECClient(user_agent=user_agent, raw_dir=raw_dir)
    importer = SECImporter(conn, client)
    return importer, client
