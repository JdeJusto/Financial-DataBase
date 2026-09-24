"""CLI entry point for the financial-database project.

Provides commands for database migration and operations.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

import click
import psycopg

from financial_database.db.migrations.runner import run_pending
from financial_database.db.migrations.runner import status as migration_status
from financial_database.providers.sec.bulk_ingest import (
    BulkImportCheckpoint,
    SECBulkIngestAbort,
    create_bulk_ingester,
)
from financial_database.providers.sec.importer import SEC_PIPELINES, create_sec_importer
from financial_database.providers.sec.models import normalize_cik
from financial_database.providers.price.yfinance_importer import YFinanceImporter


@click.group()
@click.version_option(version="0.3.0")
def cli():
    """Financial Database - PostgreSQL-first financial data platform."""


@cli.command()
@click.option("--database-url", default=None, help="PostgreSQL connection URL")
def migrate(database_url):
    """Run pending database migrations in order."""
    if database_url:
        os.environ["DATABASE_URL"] = database_url

    result = run_pending()

    if result["success"]:
        print("✅ Migrations completed successfully")
        print(f"   Applied: {result['applied_count']}")
        print(f"   Total: {result['total_applied']}")
    else:
        print(f"❌ Migration failed: {result['error']}", file=sys.stderr)
        sys.exit(1)


@cli.command()
@click.option("--database-url", default=None, help="PostgreSQL connection URL")
def status(database_url):
    """Show current migration status."""
    if database_url:
        os.environ["DATABASE_URL"] = database_url

    result = migration_status()

    print("Database Migration Status")
    print(f"  Total migrations: {result['total']}")
    print(f"  Applied: {result['applied']}")
    print(f"  Pending: {result['pending']}")
    print()

    if result["applied_names"]:
        print("  Applied:")
        for name in result["applied_names"]:
            print(f"    - {name}")

    if result["pending_names"]:
        print("  Pending:")
        for name in result["pending_names"]:
            print(f"    - {name}")


@cli.group()
def sec():
    """SEC EDGAR data ingestion commands."""


def _get_db_connection(database_url: str | None) -> psycopg.Connection:
    """Get database connection from URL or environment."""
    url = database_url or os.environ.get(
        "DATABASE_URL", "postgresql://financial:test@localhost:5432/financial_database"
    )
    return psycopg.connect(url, row_factory=psycopg.rows.dict_row)


def _get_user_agent() -> str:
    """Get SEC_USER_AGENT from environment."""
    user_agent = os.environ.get("SEC_USER_AGENT")
    if not user_agent:
        raise click.ClickException(
            "SEC_USER_AGENT environment variable is required for SEC operations. "
            "Set it in .env or export SEC_USER_AGENT='your-agent@example.com'"
        )
    return user_agent


def _get_raw_dir() -> Path:
    """Get raw data directory from environment."""
    raw_dir = os.environ.get("DATA_RAW_DIR", "./data/raw")
    return Path(raw_dir)


@sec.command("seed-provider")
@click.option("--database-url", default=None, help="PostgreSQL connection URL")
def seed_provider(database_url):
    """Seed the SEC EDGAR provider in data_providers table."""
    conn = _get_db_connection(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO data_providers (name, type, display_name, base_url, rate_limit_per_second, is_active)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (name) DO NOTHING
                   RETURNING id""",
                ("SEC EDGAR", "sec", "SEC EDGAR", "https://www.sec.gov", 10.0, True),
            )
            row = cur.fetchone()
            if row:
                print(f"✅ Created SEC provider: {row['id']}")
            else:
                cur.execute("SELECT id FROM data_providers WHERE name = 'SEC EDGAR'")
                row = cur.fetchone()
                if row:
                    print(f"✅ SEC provider already exists: {row['id']}")
        conn.commit()
    finally:
        conn.close()


@sec.command("seed-exchanges")
@click.option("--database-url", default=None, help="PostgreSQL connection URL")
def seed_exchanges(database_url):
    """Seed exchanges table with SEC exchange mappings."""
    from financial_database.db.repositories import ExchangeRepository
    from financial_database.providers.sec import get_exchange_mappings

    conn = _get_db_connection(database_url)
    try:
        repo = ExchangeRepository(conn)
        mappings = get_exchange_mappings()
        inserted = 0
        for mapping in mappings:
            result = repo.create(
                code=mapping.internal_code,
                name=mapping.internal_name,
                country=mapping.country,
                timezone=mapping.timezone,
                currency=mapping.currency,
            )
            if result:
                inserted += 1
        conn.commit()
        print(f"✅ Seeded {inserted} exchanges")
    finally:
        conn.close()


@sec.command("universe")
@click.option("--database-url", default=None, help="PostgreSQL connection URL")
@click.option("--dry-run", is_flag=True, help="Fetch data but don't write to database")
def sec_universe(database_url, dry_run):
    """Import SEC company universe (tickers, CIKs, exchanges)."""
    from financial_database.providers.sec import SECClient, SECImporter

    user_agent = _get_user_agent()
    raw_dir = _get_raw_dir()

    if dry_run:
        print("🔍 Dry run - fetching SEC company universe...")
        client = SECClient(user_agent=user_agent, raw_dir=raw_dir)
        try:
            companies = asyncio.run(client.get_company_tickers())
            print(f"   Would import {len(companies)} companies")
            for c in companies[:5]:
                print(
                    f"   - {c.cik}: {c.name} ({c.ticker or 'no ticker'}) on {c.exchange or 'no exchange'}"
                )
            if len(companies) > 5:
                print(f"   ... and {len(companies) - 5} more")
        finally:
            asyncio.run(client.close())
        return

    conn = _get_db_connection(database_url)
    client = SECClient(user_agent=user_agent, raw_dir=raw_dir)
    importer = SECImporter(conn, client)

    try:
        print("🌱 Seeding SEC provider and exchanges...")
        asyncio.run(importer.seed_exchanges())

        print("📥 Importing SEC company universe...")
        stats = asyncio.run(importer.run_import_pipeline("sec_universe"))

        print("✅ Import complete:")
        print(f"   Companies processed: {stats.companies_processed}")
        print(f"   Companies inserted: {stats.companies_inserted}")
        print(f"   Companies updated: {stats.companies_updated}")
        print(f"   Identifiers inserted: {stats.identifiers_inserted}")
        print(f"   Listings inserted: {stats.listings_inserted}")
        print(f"   Exchanges inserted: {stats.exchanges_inserted}")
        if stats.errors:
            print(f"   Errors: {len(stats.errors)}")
    finally:
        conn.close()
        asyncio.run(client.close())


@sec.command("submissions")
@click.argument("cik")
@click.option("--database-url", default=None, help="PostgreSQL connection URL")
@click.option("--dry-run", is_flag=True, help="Fetch data but don't write to database")
def sec_submissions(cik, database_url, dry_run):
    """Import SEC submissions (filings) for a specific CIK."""
    # Validate CIK format
    if not cik.isdigit():
        raise click.ClickException("CIK must contain only digits")
    # Normalize CIK to 10 digits (this will be done later anyway, but validate early)
    normalized_cik = cik.zfill(10)
    if len(normalized_cik) > 10:
        raise click.ClickException("CIK cannot be more than 10 digits")
    from financial_database.providers.sec import SECClient, SECImporter

    user_agent = _get_user_agent()
    raw_dir = _get_raw_dir()

    if dry_run:
        print(f"🔍 Dry run - fetching submissions for CIK {cik}...")
        client = SECClient(user_agent=user_agent, raw_dir=raw_dir)
        try:
            submissions = asyncio.run(client.get_submissions(cik))
            print(f"   Found {len(submissions.filings)} filings")
            for f in submissions.filings[:10]:
                print(
                    f"   - {f.form} {f.accession_number} filed {f.filing_date} period {f.period_end}"
                )
            if len(submissions.filings) > 10:
                print(f"   ... and {len(submissions.filings) - 10} more")
        finally:
            asyncio.run(client.close())
        return

    conn = _get_db_connection(database_url)
    client = SECClient(user_agent=user_agent, raw_dir=raw_dir)
    importer = SECImporter(conn, client)

    try:
        print(f"📥 Importing submissions for CIK {cik}...")
        stats = asyncio.run(importer.run_import_pipeline("sec_submissions", cik=cik))

        print("✅ Import complete:")
        print(f"   Filings processed: {stats.filings_processed}")
        print(f"   Filings inserted: {stats.filings_inserted}")
        print(f"   Filings skipped: {stats.filings_skipped}")
        if stats.errors:
            print(f"   Errors: {len(stats.errors)}")
    finally:
        conn.close()
        asyncio.run(client.close())


@sec.command("companyfacts")
@click.argument("cik")
@click.option("--database-url", default=None, help="PostgreSQL connection URL")
@click.option("--dry-run", is_flag=True, help="Fetch data but don't write to database")
def sec_companyfacts(cik, database_url, dry_run):
    """Import SEC CompanyFacts (XBRL financial facts) for a specific CIK."""
    # Validate CIK format
    if not cik.isdigit():
        raise click.ClickException("CIK must contain only digits")
    # Normalize CIK to 10 digits (this will be done later anyway, but validate early)
    normalized_cik = cik.zfill(10)
    if len(normalized_cik) > 10:
        raise click.ClickException("CIK cannot be more than 10 digits")
    from financial_database.providers.sec import SECClient, SECImporter

    user_agent = _get_user_agent()
    raw_dir = _get_raw_dir()

    if dry_run:
        print(f"🔍 Dry run - fetching CompanyFacts for CIK {cik}...")
        client = SECClient(user_agent=user_agent, raw_dir=raw_dir)
        try:
            facts = asyncio.run(client.get_company_facts(cik))
            total_values = sum(
                len(fact.values) for ns in facts.facts.values() for fact in ns.values()
            )
            print(f"   Namespaces: {len(facts.facts)}")
            print(f"   Concepts: {sum(len(ns) for ns in facts.facts.values())}")
            print(f"   Total fact values: {total_values}")
            # Show sample
            for ns, concepts in list(facts.facts.items())[:3]:
                for concept_name, fact in list(concepts.items())[:3]:
                    print(
                        f"   - {ns}:{concept_name} ({fact.unit}) - {len(fact.values)} values"
                    )
        finally:
            asyncio.run(client.close())
        return

    conn = _get_db_connection(database_url)
    client = SECClient(user_agent=user_agent, raw_dir=raw_dir)
    importer = SECImporter(conn, client)

    try:
        print(f"📥 Importing CompanyFacts for CIK {cik}...")
        stats = asyncio.run(importer.run_import_pipeline("sec_companyfacts", cik=cik))

        print("✅ Import complete:")
        print(f"   Facts processed: {stats.facts_processed}")
        print(f"   Facts inserted: {stats.facts_inserted}")
        print(f"   Facts skipped: {stats.facts_skipped}")
        print(f"   Validation errors: {stats.facts_validation_errors}")
        if stats.errors:
            print(f"   Errors: {len(stats.errors)}")
    finally:
        conn.close()
        asyncio.run(client.close())


@sec.command("sync")
@click.argument("cik")
@click.option("--database-url", default=None, help="PostgreSQL connection URL")
@click.option("--no-facts", is_flag=True, help="Skip CompanyFacts import")
@click.option("--no-filings", is_flag=True, help="Skip submissions import")
@click.option("--dry-run", is_flag=True, help="Fetch data but don't write to database")
def sec_sync(cik, database_url, no_facts, no_filings, dry_run):
    """Full sync for a single company: universe + submissions + companyfacts."""
    # Validate CIK format
    if not cik.isdigit():
        raise click.ClickException("CIK must contain only digits")
    # Normalize CIK to 10 digits (this will be done later anyway, but validate early)
    normalized_cik = cik.zfill(10)
    if len(normalized_cik) > 10:
        raise click.ClickException("CIK cannot be more than 10 digits")
    from financial_database.providers.sec import SECClient, SECImporter

    user_agent = _get_user_agent()
    raw_dir = _get_raw_dir()

    if dry_run:
        print(f"🔍 Dry run - would sync CIK {cik}")
        client = SECClient(user_agent=user_agent, raw_dir=raw_dir)
        try:
            # Just verify company exists in universe
            companies = asyncio.run(client.get_company_tickers())
            target = next(
                (c for c in companies if c.normalized_cik == cik.zfill(10)), None
            )
            if target:
                print(
                    f"   Found in universe: {target.name} ({target.ticker}) on {target.exchange}"
                )
            else:
                print(f"   ⚠️  CIK {cik} not found in SEC universe")
        finally:
            asyncio.run(client.close())
        return

    conn = _get_db_connection(database_url)
    client = SECClient(user_agent=user_agent, raw_dir=raw_dir)
    importer = SECImporter(conn, client)

    try:
        print(f"🔄 Full sync for CIK {cik}...")
        pipeline = "sec_sync"
        if no_facts and no_filings:
            pipeline = "sec_universe"
        elif no_facts:
            pipeline = "sec_submissions"
        elif no_filings:
            pipeline = "sec_companyfacts"

        stats = asyncio.run(
            importer.run_import_pipeline(
                pipeline,
                cik=cik,
            )
        )

        print("✅ Sync complete:")
        print(
            f"   Companies: {stats.companies_inserted} inserted, {stats.companies_updated} updated"
        )
        print(f"   Identifiers: {stats.identifiers_inserted} inserted")
        print(
            f"   Listings: {stats.listings_inserted} inserted, {stats.listings_updated} updated"
        )
        print(
            f"   Filings: {stats.filings_inserted} inserted, {stats.filings_skipped} skipped"
        )
        print(
            f"   Facts: {stats.facts_inserted} inserted, {stats.facts_skipped} skipped, {stats.facts_validation_errors} validation errors"
        )
        if stats.errors:
            print(f"   Errors: {len(stats.errors)}")
    finally:
        conn.close()
        asyncio.run(client.close())


@sec.command("sync-all")
@click.option("--database-url", default=None, help="PostgreSQL connection URL")
@click.option(
    "--limit", type=int, default=None, help="Limit number of companies to process"
)
@click.option(
    "--skip-universe", is_flag=True, help="Skip universe import (assume already done)"
)
@click.option("--confirm", is_flag=True, help="Confirm full universe sync (required)")
def sec_sync_all(database_url, limit, skip_universe, confirm):
    """Full universe sync - processes ALL SEC companies.

    WARNING: This will make thousands of HTTP requests and take a long time.
    Use --confirm to acknowledge.
    """
    if not confirm:
        raise click.ClickException(
            "Full universe sync requires --confirm flag. "
            "This will process thousands of companies and make extensive SEC API requests. "
            "Run with --confirm to proceed."
        )

    from financial_database.providers.sec import SECClient, SECImporter

    user_agent = _get_user_agent()
    raw_dir = _get_raw_dir()

    conn = _get_db_connection(database_url)
    client = SECClient(user_agent=user_agent, raw_dir=raw_dir)
    importer = SECImporter(conn, client)

    try:
        if not skip_universe:
            print("🌱 Seeding SEC provider and exchanges...")
            asyncio.run(importer.seed_exchanges())

            print("📥 Importing SEC company universe...")
            stats = asyncio.run(importer.import_company_universe())
            print(
                f"   Companies: {stats.companies_inserted} inserted, {stats.companies_updated} updated"
            )

        # Get all companies from database
        with conn.cursor() as cur:
            cur.execute(
                """SELECT ci.identifier_value FROM companies c
                   JOIN company_identifiers ci ON c.id = ci.company_id
                   WHERE ci.identifier_type = 'CIK' AND ci.provider_id = (
                       SELECT id FROM data_providers WHERE name = 'SEC EDGAR'
                   ) ORDER BY c.legal_name"""
            )
            ciks = [row["identifier_value"] for row in cur.fetchall()]

        if limit:
            ciks = ciks[:limit]

        print(f"🔄 Syncing {len(ciks)} companies...")
        total_stats = ImportStats()

        for i, cik in enumerate(ciks, 1):
            print(f"   [{i}/{len(ciks)}] CIK {cik}...")
            try:
                stats = asyncio.run(importer.sync_company(cik))
                total_stats.companies_processed += stats.companies_processed
                total_stats.filings_processed += stats.filings_processed
                total_stats.filings_inserted += stats.filings_inserted
                total_stats.facts_processed += stats.facts_processed
                total_stats.facts_inserted += stats.facts_inserted
                total_stats.errors.extend(stats.errors)
            except Exception as e:  # noqa: BLE001 - catch all to continue with other companies
                print(f"      ❌ Failed: {e}")
                total_stats.errors.append({"cik": cik, "error": str(e)})

        print("✅ Full sync complete:")
        print(f"   Companies processed: {total_stats.companies_processed}")
        print(f"   Filings inserted: {total_stats.filings_inserted}")
        print(f"   Facts inserted: {total_stats.facts_inserted}")
        print(f"   Total errors: {len(total_stats.errors)}")
    finally:
        conn.close()
        asyncio.run(client.close())


@sec.command("bulk-ingest")
@click.option("--database-url", default=None, help="PostgreSQL connection URL")
@click.option(
    "--data-dir", default=None, help="Directory containing extracted SEC bulk files"
)
@click.option(
    "--download", is_flag=True, help="Download latest bulk files from SEC first"
)
@click.option(
    "--checkpoint-file", default=None, help="Path to a checkpoint file for resumability"
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Process only first N companies (for testing)",
)
@click.option("--dry-run", is_flag=True, help="Validate without writing to PostgreSQL")
@click.option("--verbose", is_flag=True, help="Increase logging detail")
@click.option(
    "--confirm", is_flag=True, help="Confirm bulk ingestion (required for full run)"
)
@click.option(
    "--force", is_flag=True, help="Ignore previous checkpoint and start from scratch"
)
@click.option(
    "--api-mode", is_flag=True, default=True, help="Use SEC API for ingestion (default)"
)
def sec_bulk_ingest(
    database_url: str | None,
    data_dir: str | None,
    download: bool,
    checkpoint_file: str | None,
    limit: int | None,
    dry_run: bool,
    verbose: bool,
    confirm: bool,
    force: bool,
    api_mode: bool,
):
    """Full historical SEC EDGAR bulk ingestion using companyfacts.zip and submissions.zip.

    WARNING: This processes ALL SEC companies and can take many hours. Use
    --confirm to acknowledge, or --limit for testing.
    """

    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if limit is not None and limit <= 0:
        raise click.ClickException("--limit must be a positive integer greater than 0")

    if limit is None and not confirm and not dry_run:
        raise click.ClickException(
            "Bulk ingestion processes thousands of companies and takes hours. "
            "Use --confirm to proceed, or --limit N for testing, or --dry-run to validate."
        )

    if dry_run:
        print("🔍 Dry run - validating bulk ingestion setup...")
        print(
            f"   Checkpoint file: {checkpoint_file or 'default (./data/checkpoints/sec_bulk/full_universe_checkpoint.json)'}"
        )
        print(f"   Limit: {limit or 'none (all companies)'}")
        print(f"   Download: {'yes' if download else 'no'}")
        print(f"   Force (ignore checkpoint): {'yes' if force else 'no'}")

        from financial_database.providers.sec import SECClient

        user_agent = _get_user_agent()
        raw_dir = _get_raw_dir()
        client = SECClient(user_agent=user_agent, raw_dir=raw_dir)
        try:
            companies = asyncio.run(client.get_company_tickers())
            total = len(companies)
            if limit and limit > 0:
                companies = companies[:limit]
            print(f"   Companies loaded: {len(companies)} (of {total} total)")
            for c in companies[:5]:
                print(
                    f"   - {c.cik}: {c.name} ({c.ticker or 'no ticker'}) on {c.exchange or 'no exchange'}"
                )
        finally:
            asyncio.run(client.close())
        return

    # Get database connection URL
    database_url = database_url or os.environ.get(
        "DATABASE_URL", "postgresql://financial:test@localhost:5432/financial_database"
    )

    user_agent = _get_user_agent()
    raw_dir = Path(data_dir) if data_dir else _get_raw_dir()

    start_time = time.time()

    # Create bulk ingester
    print("🔧 Initializing bulk ingester...")
    ingester, client = asyncio.run(
        create_bulk_ingester(
            database_url=database_url,
            user_agent=user_agent,
            raw_dir=raw_dir,
            checkpoint_dir=Path(checkpoint_file).parent if checkpoint_file else None,
        )
    )

    # Load checkpoint if provided (skipped when --force is set)
    checkpoint = None
    if checkpoint_file and Path(checkpoint_file).exists() and not force:
        print(f"📌 Loading checkpoint from {checkpoint_file}")
        with open(checkpoint_file) as f:
            data = json.load(f)
        checkpoint = BulkImportCheckpoint.from_dict(data)
        print(f"   Resuming from CIK: {checkpoint.last_processed_cik or 'beginning'}")
        print(f"   Companies processed so far: {checkpoint.companies_processed}")

    if force:
        print("🔄 Force flag set: ignoring previous checkpoint progress")

    async def run_with_signals():
        # Install signal handlers for graceful shutdown
        client.install_signal_handlers()

        return await ingester.ingest_full_universe(
            checkpoint=checkpoint,
            limit=limit,
            delay_between_requests=0.1,
            force=force,
        )

    try:
        stats = asyncio.run(run_with_signals())

        elapsed = time.time() - start_time

        print("\n✅ Bulk ingestion complete:")
        print(f"   Companies processed: {stats.companies_processed}")
        print(f"   Companies inserted: {stats.companies_inserted}")
        print(f"   Companies updated: {stats.companies_updated}")
        print(f"   Identifiers inserted: {stats.identifiers_inserted}")
        print(f"   Filings processed: {stats.filings_processed}")
        print(f"   Filings inserted: {stats.filings_inserted}")
        print(f"   Filings skipped: {stats.filings_skipped}")
        print(f"   Facts processed: {stats.facts_processed}")
        print(f"   Facts inserted: {stats.facts_inserted}")
        print(f"   Facts skipped: {stats.facts_skipped}")
        print(f"   Facts validation errors: {stats.facts_validation_errors}")
        print(f"   Errors encountered: {len(stats.errors)}")
        print(f"   Elapsed time: {elapsed:.1f}s ({elapsed / 60:.1f}min)")

        if stats.errors:
            print("\n⚠️  Errors (first 5):")
            for err in stats.errors[:5]:
                print(f"   - {err}")

    except (OSError, psycopg.Error, RuntimeError, ValueError) as e:
        ingester.mark_import_run_failed(str(e))
        print(f"�⚠ Bulk ingestion failed: {e}", file=sys.stderr)
        logging.getLogger(__name__).exception("Bulk ingestion failed")
        sys.exit(1)
    except SECBulkIngestAbort as e:
        ingester.mark_import_run_failed(str(e))
        print(f"❌ Bulk ingestion aborted: {e}", file=sys.stderr)
        print("   Checkpoint saved; resume later with the same command.")
        sys.exit(1)
    except asyncio.CancelledError:
        print("\n⚠️  Ingestion interrupted by signal, checkpoint saved for resume")
        sys.exit(130)
    finally:
        asyncio.run(client.close())


@sec.command("update-incremental")
@click.option("--database-url", default=None, help="PostgreSQL connection URL")
@click.option(
    "--max-age-hours",
    type=int,
    default=24,
    help="Maximum age of data before considering it stale (default: 24 hours)",
)
@click.option(
    "--batch-size",
    type=int,
    default=100,
    help="Number of companies to process in each batch (default: 100)",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Limit number of companies to process (for testing)",
)
@click.option("--dry-run", is_flag=True, help="Validate without writing to database")
@click.option("--verbose", is_flag=True, help="Increase logging detail")
def sec_update_incremental(
    database_url: str | None,
    max_age_hours: int,
    batch_size: int,
    limit: int | None,
    dry_run: bool,
    verbose: bool,
):
    """Incrementally update the database with latest SEC data.

    This command:
    1. Downloads the latest company_tickers.json
    2. Identifies companies that have new or changed data
    3. For each changed company, fetches latest submissions and companyfacts
    4. Upserts the data using existing idempotent repositories
    5. Records an import_run with status success/partial/failed

    Safe to run multiple times per day.
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if dry_run:
        print("🔍 Dry run - validating incremental update setup...")
        print(f"   Max age: {max_age_hours} hours")
        print(f"   Batch size: {batch_size}")
        if limit is not None and limit > 0:
            print(f"   Limit: {limit} (will be applied to processing)")

        from financial_database.providers.sec import SECClient

        user_agent = _get_user_agent()
        raw_dir = _get_raw_dir()
        client = SECClient(user_agent=user_agent, raw_dir=raw_dir)
        try:
            companies = asyncio.run(client.get_company_tickers())
            if limit is not None and limit > 0:
                companies = companies[:limit]
            print(
                f"   Companies in SEC universe: {len(companies)}{' (limited)' if limit is not None and limit > 0 else ''}"
            )
            # Check how many would be considered stale
            conn = _get_db_connection(database_url)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COUNT(*)
                        FROM companies c
                        JOIN company_identifiers ci ON c.id = ci.company_id
                        WHERE ci.identifier_type = 'CIK'
                          AND ci.provider_id = (SELECT id FROM data_providers WHERE name = 'SEC EDGAR')
                          AND (c.last_synced_at IS NULL OR c.last_synced_at < NOW() - (%s * interval '1 hour'))
                        """,
                        (max_age_hours,),
                    )
                    result = cur.fetchone()
                    stale_count = result["count"] if result else 0
                    print(f"   Stale companies (>{max_age_hours}h): {stale_count}")
                    if limit is not None and limit > 0:
                        print(
                            f"   Note: --limit {limit} will be applied to the list of stale companies for processing."
                        )
            finally:
                conn.close()
        finally:
            asyncio.run(client.close())
        return

    async def _run_update_incremental():
        # Get database connection
        effective_database_url = database_url or os.environ.get(
            "DATABASE_URL",
            "postgresql://financial:test@localhost:5432/financial_database",
        )

        user_agent = _get_user_agent()
        raw_dir = _get_raw_dir()

        start_time = time.time()

        # Create importer
        print("🔧 Initializing incremental updater...")
        importer, client = create_sec_importer(
            database_url=effective_database_url,
            user_agent=user_agent,
            raw_dir=raw_dir,
        )

        try:
            # Record the import run for audit/provenance
            provider_id = importer._get_provider_id()
            # Flag SEC import runs left dangling in 'running' by a previous
            # crashed/killed process before recording this fresh run.
            importer.import_runs.mark_dangling_running(
                str(provider_id), list(SEC_PIPELINES)
            )
            run = importer.import_runs.create(
                str(provider_id), "sec_update_incremental", "running"
            )
            run_id = str(run["id"])
            run_start_time = time.time()

            print("📥 Fetching latest company universe from SEC...")
            sec_companies = await client.get_company_tickers()
            sec_company_dict = {normalize_cik(c.cik): c for c in sec_companies}
            print(f"   Found {len(sec_companies)} companies in SEC universe")

            # Get companies from database that need updating
            print("🔍 Identifying stale companies...")
            conn = importer.conn  # Reuse the connection from importer
            stale_ciks = []

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ci.identifier_value
                    FROM companies c
                    JOIN company_identifiers ci ON c.id = ci.company_id
                    WHERE ci.identifier_type = 'CIK'
                      AND ci.provider_id = (SELECT id FROM data_providers WHERE name = 'SEC EDGAR')
                      AND (c.last_synced_at IS NULL OR c.last_synced_at < NOW() - (%s * interval '1 hour'))
                    """,
                    (max_age_hours,),
                )
                result = cur.fetchall()
                stale_ciks = (
                    [row["identifier_value"] for row in result] if result else []
                )

            # Apply the --limit option (it previously only affected dry-run)
            if limit is not None and limit > 0:
                stale_ciks = stale_ciks[:limit]

            print(
                f"   Found {len(stale_ciks)} companies needing update (>{max_age_hours}h stale)"
            )

            if not stale_ciks:
                print("✅ No companies need updating - all data is fresh!")
                # Still mark the import run as successful
                importer.import_runs.update(
                    run_id,
                    status="success",
                    records_processed=0,
                    records_inserted=0,
                    records_updated=0,
                    records_skipped=0,
                    finished_at=datetime.now(UTC),
                    duration_seconds=int(time.time() - run_start_time),
                )
                return

            # Process in batches
            total_stats = ImportStats()
            processed_count = 0

            for i in range(0, len(stale_ciks), batch_size):
                batch = stale_ciks[i : i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(stale_ciks) + batch_size - 1) // batch_size

                print(
                    f"📦 Processing batch {batch_num}/{total_batches} ({len(batch)} companies)..."
                )

                batch_stats = ImportStats()

                for cik in batch:
                    # Get the SEC company data
                    sec_company = sec_company_dict.get(cik)
                    if not sec_company:
                        logger.warning(f"CIK {cik} not found in SEC universe, skipping")
                        batch_stats.errors.append(
                            {"cik": cik, "error": "CIK not found in SEC universe"}
                        )
                        continue

                    try:
                        # Sync this company (universe + submissions + companyfacts)
                        company_stats = await importer.sync_company(
                            cik,
                            include_facts=True,
                            include_filings=True,
                            stats=ImportStats(),
                        )

                        # Update the last_synced timestamp
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                UPDATE companies
                                SET last_synced_at = NOW()
                                WHERE id = (
                                    SELECT c.id
                                    FROM companies c
                                    JOIN company_identifiers ci ON c.id = ci.company_id
                                    WHERE ci.identifier_type = 'CIK'
                                      AND ci.identifier_value = %s
                                      AND ci.provider_id = (SELECT id FROM data_providers WHERE name = 'SEC EDGAR')
                                )
                                """,
                                (cik,),
                            )

                        # Accumulate stats
                        batch_stats.companies_processed += (
                            company_stats.companies_processed
                        )
                        batch_stats.companies_inserted += (
                            company_stats.companies_inserted
                        )
                        batch_stats.companies_updated += company_stats.companies_updated
                        batch_stats.identifiers_inserted += (
                            company_stats.identifiers_inserted
                        )
                        batch_stats.listings_inserted += company_stats.listings_inserted
                        batch_stats.filings_processed += company_stats.filings_processed
                        batch_stats.filings_inserted += company_stats.filings_inserted
                        batch_stats.filings_skipped += company_stats.filings_skipped
                        batch_stats.facts_processed += company_stats.facts_processed
                        batch_stats.facts_inserted += company_stats.facts_inserted
                        batch_stats.facts_skipped += company_stats.facts_skipped
                        batch_stats.facts_validation_errors += (
                            company_stats.facts_validation_errors
                        )
                        batch_stats.errors.extend(company_stats.errors)

                        processed_count += 1

                    except Exception as e:  # noqa: BLE001 - catch all to continue with other companies
                        logger.error(f"Failed to process company {cik}: {e}")
                        batch_stats.errors.append(
                            {"cik": cik, "error": str(e), "type": type(e).__name__}
                        )

                # Commit after each batch
                conn.commit()

                # Accumulate batch stats to total
                total_stats.companies_processed += batch_stats.companies_processed
                total_stats.companies_inserted += batch_stats.companies_inserted
                total_stats.companies_updated += batch_stats.companies_updated
                total_stats.identifiers_inserted += batch_stats.identifiers_inserted
                total_stats.listings_inserted += batch_stats.listings_inserted
                total_stats.filings_processed += batch_stats.filings_processed
                total_stats.filings_inserted += batch_stats.filings_inserted
                total_stats.filings_skipped += batch_stats.filings_skipped
                total_stats.facts_processed += batch_stats.facts_processed
                total_stats.facts_inserted += batch_stats.facts_inserted
                total_stats.facts_skipped += batch_stats.facts_skipped
                total_stats.facts_validation_errors += (
                    batch_stats.facts_validation_errors
                )
                total_stats.errors.extend(batch_stats.errors)

                print(
                    f"   ✅ Batch {batch_num} complete: {batch_stats.companies_processed} companies processed"
                )

            # Finalize import run
            duration = int(time.time() - run_start_time)
            error_dict = None
            if total_stats.errors:
                error_dict = {
                    "error_count": len(total_stats.errors),
                    "sample_errors": total_stats.errors[:5],
                }

            importer.import_runs.update(
                run_id,
                status="success" if len(total_stats.errors) == 0 else "partial",
                records_processed=total_stats.companies_processed
                + total_stats.filings_processed
                + total_stats.facts_processed,
                records_inserted=total_stats.companies_inserted
                + total_stats.filings_inserted
                + total_stats.facts_inserted,
                records_updated=total_stats.companies_updated
                + total_stats.listings_inserted,
                records_skipped=total_stats.filings_skipped + total_stats.facts_skipped,
                errors=error_dict,
                finished_at=datetime.now(UTC),
                duration_seconds=duration,
            )

            elapsed = time.time() - start_time
            print("\n✅ Incremental update complete:")
            print(f"   Companies processed: {total_stats.companies_processed}")
            print(f"   Companies inserted: {total_stats.companies_inserted}")
            print(f"   Companies updated: {total_stats.companies_updated}")
            print(f"   Identifiers inserted: {total_stats.identifiers_inserted}")
            print(f"   Filings processed: {total_stats.filings_processed}")
            print(f"   Filings inserted: {total_stats.filings_inserted}")
            print(f"   Filings skipped: {total_stats.filings_skipped}")
            print(f"   Facts processed: {total_stats.facts_processed}")
            print(f"   Facts inserted: {total_stats.facts_inserted}")
            print(f"   Facts skipped: {total_stats.facts_skipped}")
            print(f"   Facts validation errors: {total_stats.facts_validation_errors}")
            print(f"   Errors encountered: {len(total_stats.errors)}")
            print(f"   Elapsed time: {elapsed:.1f}s ({elapsed / 60:.1f}min)")

            if total_stats.errors:
                print("\n⚠️  Errors (first 5):")
                for err in total_stats.errors[:5]:
                    print(f"   - {err}")

        except Exception as e:
            # Mark the import run as failed
            if "run_id" in locals():
                importer.import_runs.update(
                    run_id,
                    status="failed",
                    records_processed=0,
                    records_inserted=0,
                    records_updated=0,
                    records_skipped=0,
                    errors={"error": str(e), "type": type(e).__name__},
                    finished_at=datetime.now(UTC),
                    duration_seconds=int(time.time() - run_start_time),
                )

            print(f"❌ Incremental update failed: {e}", file=sys.stderr)
            logging.getLogger(__name__).exception("Incremental update failed")
            sys.exit(1)
        finally:
            await client.close()

    # Run the async function
    asyncio.run(_run_update_incremental())


# Import Stats class for type hints
from financial_database.providers.sec import ImportStats


@cli.group()
def prices():
    """Stock price ingestion commands."""
    pass


@prices.command("update")
@click.option("--database-url", default=None, help="PostgreSQL connection URL")
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Limit number of listings to process (for testing)",
)
@click.option("--dry-run", is_flag=True, help="Validate without writing to database")
@click.option("--verbose", is_flag=True, help="Increase logging detail")
def prices_update(
    database_url: str | None,
    limit: int | None,
    dry_run: bool,
    verbose: bool,
):
    """Update stock prices from Yahoo Finance for all active listings."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if dry_run:
        print("🔍 Dry run - validating price update setup...")
        print(f"   Limit: {limit or 'none (all listings)'}")
        # We could do a quick check here, but for simplicity we just show the config.
        return

    async def _run_price_update():
        # Get database connection
        effective_database_url = database_url or os.environ.get(
            "DATABASE_URL",
            "postgresql://financial:test@localhost:5432/financial_database",
        )

        start_time = time.time()

        # Create importer
        print("🔧 Initializing price updater...")
        importer = YFinanceImporter(database_url=effective_database_url)

        try:
            # Record the import run for audit/provenance
            provider = importer.provider_repo.get_by_name("Yahoo Finance")
            if not provider:
                # This should not happen because the importer creates it if missing, but just in case.
                provider = importer.provider_repo.create(
                    {
                        "name": "Yahoo Finance",
                        "type": "price",
                        "display_name": "Yahoo Finance",
                        "base_url": "https://finance.yahoo.com",
                        "is_active": True,
                    }
                )
            provider_id = str(provider["id"])
            run = importer.import_runs.create(
                str(provider_id), "prices_update", "running"
            )
            run_id = str(run["id"])
            run_start_time = time.time()

            print("📥 Fetching latest prices from Yahoo Finance...")
            stats = await importer.run(limit=limit)

            # Finalize import run
            duration = int(time.time() - run_start_time)
            error_dict = None
            if stats.errors:
                error_dict = {
                    "error_count": len(stats.errors),
                    "sample_errors": stats.errors[:5],
                }

            importer.import_runs.update(
                run_id,
                status="success" if len(stats.errors) == 0 else "partial",
                records_processed=stats.records_processed,
                records_inserted=stats.records_inserted,
                records_updated=stats.records_updated,
                records_skipped=stats.records_skipped,
                errors=error_dict,
                finished_at=datetime.now(UTC),
                duration_seconds=duration,
            )

            elapsed = time.time() - start_time
            print("\n✅ Price update complete:")
            print(f"   Listings processed: {stats.records_processed}")
            print(f"   Prices inserted: {stats.records_inserted}")
            print(f"   Prices updated: {stats.records_updated}")
            print(f"   Prices skipped: {stats.records_skipped}")
            print(f"   Errors encountered: {len(stats.errors)}")
            print(f"   Elapsed time: {elapsed:.1f}s ({elapsed / 60:.1f}min)")

            if stats.errors:
                print("\n⚠️  Errors (first 5):")
                for err in stats.errors[:5]:
                    print(f"   - {err}")

        except Exception as e:
            # Mark the import run as failed
            if "run_id" in locals():
                importer.import_runs.update(
                    run_id,
                    status="failed",
                    records_processed=0,
                    records_inserted=0,
                    records_updated=0,
                    records_skipped=0,
                    errors={"error": str(e), "type": type(e).__name__},
                    finished_at=datetime.now(UTC),
                    duration_seconds=int(time.time() - run_start_time),
                )

            print(f"❌ Price update failed: {e}", file=sys.stderr)
            logging.getLogger(__name__).exception("Price update failed")
            sys.exit(1)

    # Run the async function
    asyncio.run(_run_price_update())


@cli.command()
@click.option("--database-url", default=None, help="PostgreSQL connection URL")
@click.option(
    "--sec-max-age-hours",
    type=int,
    default=24,
    help="Maximum age of SEC data before considering it stale (default: 24 hours)",
)
@click.option(
    "--sec-batch-size",
    type=int,
    default=100,
    help="Number of companies to process in each batch for SEC update (default: 100)",
)
@click.option(
    "--sec-limit",
    type=int,
    default=None,
    help="Limit number of companies to process for SEC update (for testing)",
)
@click.option(
    "--price-limit",
    type=int,
    default=None,
    help="Limit number of listings to process for price update (for testing)",
)
@click.option("--dry-run", is_flag=True, help="Validate without writing to database")
@click.option("--verbose", is_flag=True, help="Increase logging detail")
def update_all(
    database_url: str | None,
    sec_max_age_hours: int,
    sec_batch_size: int,
    sec_limit: int | None,
    price_limit: int | None,
    dry_run: bool,
    verbose: bool,
):
    """Run both SEC incremental update and stock price update.

    This command runs:
    1. financial-db sec update-incremental (with given options)
    2. financial-db prices update (with given options)

    Safe to run daily.
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if dry_run:
        print("🔍 Dry run - validating update-all setup...")
        print(f"   SEC max age: {sec_max_age_hours} hours")
        print(f"   SEC batch size: {sec_batch_size}")
        if sec_limit is not None and sec_limit > 0:
            print(f"   SEC limit: {sec_limit}")
        if price_limit is not None and price_limit > 0:
            print(f"   Price limit: {price_limit}")
        # We could do a quick check here, but for simplicity we just show the config.
        return

    # Run SEC incremental update
    print("🚀 Starting SEC incremental update...")
    # We'll reuse the same logic from sec_update_incremental by calling its callback via subprocess
    # to avoid code duplication while keeping the implementation simple
    sec_cmd = [
        sys.executable,
        "-m",
        "financial_database.cli",
        "sec",
        "update-incremental",
    ]
    if database_url:
        sec_cmd.extend(["--database-url", database_url])
    sec_cmd.extend(["--max-age-hours", str(sec_max_age_hours)])
    sec_cmd.extend(["--batch-size", str(sec_batch_size)])
    if sec_limit is not None:
        sec_cmd.extend(["--limit", str(sec_limit)])
    if dry_run:
        sec_cmd.append("--dry-run")
    if verbose:
        sec_cmd.append("--verbose")

    try:
        result = subprocess.run(sec_cmd, check=True, capture_output=False, text=True)
        if result.returncode != 0:
            print(f"❌ SEC incremental update failed with return code {result.returncode}")
            sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        print(f"❌ SEC incremental update failed: {e}")
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("❌ Could not find financial_database.cli module. Make sure the package is installed correctly.")
        sys.exit(1)

    # Run price update
    print("\n🚀 Starting price update...")
    price_cmd = [
        sys.executable,
        "-m",
        "financial_database.cli",
        "prices",
        "update",
    ]
    if database_url:
        price_cmd.extend(["--database-url", database_url])
    if price_limit is not None:
        price_cmd.extend(["--limit", str(price_limit)])
    if dry_run:
        price_cmd.append("--dry-run")
    if verbose:
        price_cmd.append("--verbose")

    try:
        result = subprocess.run(price_cmd, check=True, capture_output=False, text=True)
        if result.returncode != 0:
            print(f"❌ Price update failed with return code {result.returncode}")
            sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        print(f"❌ Price update failed: {e}")
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("❌ Could not find financial_database.cli module. Make sure the package is installed correctly.")
        sys.exit(1)

    print("\n✅ All updates completed successfully!")


if __name__ == "__main__":
    cli()
