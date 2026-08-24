"""CLI entry point for the financial-database project.

Provides commands for database migration and operations.
"""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

import click
import psycopg

from financial_database.db.migrations.runner import run_pending
from financial_database.db.migrations.runner import status as migration_status


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
    "--checkpoint-file", default=None, help="Path to checkpoint file for resumability"
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
def sec_bulk_ingest(
    database_url, data_dir, download, checkpoint_file, limit, dry_run, verbose, confirm
):
    """Full historical SEC EDGAR bulk ingestion using companyfacts.zip and submissions.zip.

    WARNING: This processes ALL SEC companies and can take many hours.
    Use --confirm to acknowledge, or --limit for testing.
    """

    logger = logging.getLogger(__name__)

    from financial_database.providers.sec.bulk_ingest import (
        BulkImportCheckpoint,
        create_bulk_ingester,
    )

    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Check confirmation for full runs
    if limit is None and not confirm and not dry_run:
        raise click.ClickException(
            "Bulk ingestion processes thousands of companies and takes hours. "
            "Use --confirm to proceed, or --limit N for testing, or --dry-run to validate."
        )

    start_time = time.time()

    if dry_run:
        print("🔍 Dry run - validating bulk ingestion setup...")
        print(
            f"   Data directory: {data_dir or 'default (./data/raw/sec/bulk_downloads)'}"
        )
        print(
            f"   Checkpoint file: {checkpoint_file or 'default (./data/checkpoints/sec_bulk/companyfacts_checkpoint.json)'}"
        )
        print(f"   Limit: {limit or 'none (all companies)'}")
        print(f"   Download: {'yes' if download else 'no'}")
        return

    # Get database connection
    url = database_url or os.environ.get(
        "DATABASE_URL", "postgresql://financial:test@localhost:5432/financial_database"
    )
    conn = psycopg.connect(url, row_factory=psycopg.rows.dict_row)

    user_agent = _get_user_agent()
    raw_dir = Path(data_dir) if data_dir else _get_raw_dir()

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

    try:
        companyfacts_path = None

        if download:
            print("📥 Downloading SEC bulk files...")
            downloaded = asyncio.run(ingester.download_bulk_files(force=False))
            companyfacts_zip = downloaded.get("companyfacts")
            if companyfacts_zip:
                print("📦 Extracting companyfacts.zip...")
                extracted = asyncio.run(
                    ingester.extract_zip(companyfacts_zip, raw_dir / "bulk_extracted")
                )
                for f in extracted:
                    if f.name == "companyfacts.json":
                        companyfacts_path = f
                        break

        if not companyfacts_path:
            # Look for existing extracted file
            search_dir = Path(data_dir) if data_dir else raw_dir / "bulk_extracted"
            companyfacts_path = search_dir / "companyfacts.json"
            if not companyfacts_path.exists():
                # Try default location
                companyfacts_path = raw_dir / "bulk_downloads" / "companyfacts.json"
            if not companyfacts_path.exists():
                raise click.ClickException(
                    "companyfacts.json not found. Use --download to fetch, or --data-dir to specify location."
                )

        print(f"📂 Using companyfacts file: {companyfacts_path}")

        # Load checkpoint if provided
        checkpoint = None
        if checkpoint_file and Path(checkpoint_file).exists():
            print(f"📌 Loading checkpoint from {checkpoint_file}")
            with open(checkpoint_file) as f:
                data = json.load(f)
            checkpoint = BulkImportCheckpoint.from_dict(data)
            print(
                f"   Resuming from CIK: {checkpoint.last_processed_cik or 'beginning'}"
            )
            print(f"   Companies processed so far: {checkpoint.companies_processed}")

        print("🚀 Starting bulk ingestion of CompanyFacts...")
        stats = asyncio.run(
            ingester.ingest_companyfacts(
                companyfacts_path,
                checkpoint=checkpoint,
                limit=limit,
            )
        )

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
        print(f"❌ Bulk ingestion failed: {e}", file=sys.stderr)
        logger.exception("Bulk ingestion failed")
        sys.exit(1)
    finally:
        conn.close()
        asyncio.run(client.close())


# Import Stats class for type hints
from financial_database.providers.sec import ImportStats

if __name__ == "__main__":
    cli()
