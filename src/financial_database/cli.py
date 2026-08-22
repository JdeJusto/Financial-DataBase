"""CLI entry point for the financial-database project.

Provides commands for database migration and operations.
"""

import sys
import click


@click.group()
@click.version_option(version="0.2.0")
def cli():
    """Financial Database - PostgreSQL-first financial data platform."""
    pass


@cli.command()
@click.option("--database-url", default=None, help="PostgreSQL connection URL")
def migrate(database_url):
    """Run pending database migrations in order."""
    import os
    from financial_database.db.migrations.runner import run_pending

    if database_url:
        os.environ["DATABASE_URL"] = database_url

    result = run_pending()

    if result["success"]:
        print(f"✅ Migrations completed successfully")
        print(f"   Applied: {result['applied_count']}")
        print(f"   Total: {result['total_applied']}")
    else:
        print(f"❌ Migration failed: {result['error']}", file=sys.stderr)
        sys.exit(1)


@cli.command()
@click.option("--database-url", default=None, help="PostgreSQL connection URL")
def status(database_url):
    """Show current migration status."""
    import os
    from financial_database.db.migrations.runner import status

    if database_url:
        os.environ["DATABASE_URL"] = database_url

    result = status()

    print(f"Database Migration Status")
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


if __name__ == "__main__":
    cli()