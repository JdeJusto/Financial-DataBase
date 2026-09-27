"""Unit tests for migration runner."""

from pathlib import Path

import pytest


class TestMigrationDiscovery:
    """Test that migrations can be discovered."""

    def test_migrations_dir_exists(self):
        """Test that migrations directory exists."""
        migrations_dir = Path(__file__).parent.parent.parent / "db" / "migrations"
        assert migrations_dir.exists()

    def test_has_21_migrations(self):
        """Test that we have exactly 21 migrations."""
        migrations_dir = Path(__file__).parent.parent.parent / "db" / "migrations"
        sql_files = list(migrations_dir.glob("*.sql"))
        assert len(sql_files) == 21

    def test_migrations_are_numbered(self):
        """Test that all migrations are properly numbered."""
        migrations_dir = Path(__file__).parent.parent.parent / "db" / "migrations"
        sql_files = list(migrations_dir.glob("*.sql"))
        names = [f.stem for f in sql_files]
        for name in names:
            # Should start with 4-digit number
            assert name[:4].isdigit(), f"Migration {name} not properly numbered"

    def test_migration_order(self):
        """Test that migrations are in correct order."""
        migrations_dir = Path(__file__).parent.parent.parent / "db" / "migrations"
        sql_files = sorted(migrations_dir.glob("*.sql"))
        names = [f.stem for f in sql_files]

        expected = [
            "0001_extensions",
            "0002_data_providers",
            "0003_exchanges",
            "0004_companies",
            "0005_company_identifiers",
            "0006_company_listings",
            "0007_filings",
            "0008_financial_facts",
            "0009_prices",
            "0010_dividends",
            "0011_splits",
            "0012_raw_documents",
            "0013_import_runs",
            "0014_indexes",
            "0015_sec_provider_seed",
            "0016_fix_duplicate_listings",
            "0017_fix_filings_nullable_period",
            "0018_add_namespace_frame_to_financial_facts",
            "0019_fix_financial_facts_dedup",
            "0020_extend_financial_facts_columns",
            "0021_import_runs_company_id",
        ]
        assert names == expected


class TestMigrationRunner:
    """Test migration runner functions."""

    def test_find_project_root(self):
        """Test that find_project_root works."""
        from financial_database.db.migrations.runner import find_project_root

        root = find_project_root()
        # The project root can be either "financial-database" or "Financial-DataBase" depending on case
        assert root.name.lower() == "financial-database"
        assert (root / "pyproject.toml").exists()

    def test_get_migration_files(self):
        """Test getting migration files."""
        from financial_database.db.migrations.runner import get_migration_files

        files = get_migration_files()
        assert len(files) == 21
        assert all(isinstance(f, tuple) and len(f) == 2 for f in files)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
