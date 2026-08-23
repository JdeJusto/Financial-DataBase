"""Migration runner for the financial-database project.

Manages PostgreSQL schema migrations stored in db/migrations/.
"""

import os
from pathlib import Path

import psycopg


def find_project_root() -> Path:
    """Find the project root by looking for pyproject.toml."""
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "pyproject.toml").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return Path(__file__).resolve().parent.parent.parent.parent


PROJECT_ROOT = find_project_root()
MIGRATIONS_DIR = PROJECT_ROOT / "db" / "migrations"
APPLIED_TABLE = "schema_migrations"


def get_connection():
    """Get PostgreSQL connection from environment variables."""
    database_url = os.environ.get(
        "DATABASE_URL", "postgresql://financial:test@localhost:5432/financial_database"
    )
    return psycopg.connect(database_url, row_factory=psycopg.rows.dict_row)


def ensure_applied_table(conn):
    """Create the schema_migrations table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {APPLIED_TABLE} (
                id SERIAL PRIMARY KEY,
                migration_name VARCHAR(255) NOT NULL UNIQUE,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
    conn.commit()


def get_applied_migrations(conn) -> set:
    """Get set of already-applied migration names."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT migration_name FROM {APPLIED_TABLE}")
        return {row["migration_name"] for row in cur.fetchall()}


def get_migration_files() -> list:
    """Get sorted list of migration SQL files."""
    files = []
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        name = f.stem
        files.append((name, f))
    return files


def run_pending() -> dict:
    """Run pending migrations in order.

    Returns dict with success status and counts.
    """
    conn = get_connection()
    try:
        conn.autocommit = False

        ensure_applied_table(conn)

        applied = get_applied_migrations(conn)

        all_migrations = get_migration_files()
        pending = [(name, f) for name, f in all_migrations if name not in applied]

        if not pending:
            return {
                "success": True,
                "applied_count": 0,
                "total_applied": len(applied),
                "message": "No pending migrations",
            }

        applied_count = 0

        for name, migration_file in pending:
            try:
                with open(migration_file, "r") as f:
                    sql = f.read()

                with conn.cursor() as cur:
                    cur.execute(sql)  # pyright: ignore[reportCallIssue, reportArgumentType]

                with conn.cursor() as cur:
                    cur.execute(
                        f"INSERT INTO {APPLIED_TABLE} (migration_name) VALUES (%s)",
                        (name,),
                    )

                conn.commit()
                applied_count += 1
                print(f"✅ Applied migration: {name}")

            except Exception:
                conn.rollback()
                raise

        return {
            "success": True,
            "applied_count": applied_count,
            "total_applied": len(applied) + applied_count,
            "message": f"Applied {applied_count} pending migrations",
        }

    finally:
        conn.close()


def status() -> dict:
    """Get current migration status."""
    conn = get_connection()
    try:
        ensure_applied_table(conn)
        applied = get_applied_migrations(conn)
        all_migrations = get_migration_files()

        pending = [name for name, _ in all_migrations if name not in applied]

        return {
            "total": len(all_migrations),
            "applied": len(applied),
            "pending": len(pending),
            "applied_names": sorted(applied),
            "pending_names": sorted(pending),
        }
    finally:
        conn.close()
