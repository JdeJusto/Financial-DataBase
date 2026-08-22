"""Import run repository.

Audit metadata for import pipelines.
Tracks provenance of data loading operations.
"""

from financial_database.db.connection import get_connection


class ImportRunRepository:
    """Repository for import_runs table."""

    def __init__(self, conn):
        self.conn = conn

    def create(self, provider_id: str, pipeline: str, status: str = "running") -> dict:
        """Create a new import run record."""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO import_runs (provider_id, pipeline, status)
                   VALUES (%s, %s, %s)
                   RETURNING id, provider_id, pipeline, status, records_processed, records_inserted,
                   records_updated, records_skipped, errors, started_at, finished_at,
                   duration_seconds""",
                (provider_id, pipeline, status)
            )
            return cur.fetchone()

    def update(self, run_id: str, status: str | None = None,
               records_processed: int | None = None,
               records_inserted: int | None = None,
               records_updated: int | None = None,
               records_skipped: int | None = None,
               errors: dict | None = None,
               finished_at = None, duration_seconds: int | None = None) -> None:
        """Update an import run record."""
        set_parts = []
        params = []

        if status is not None:
            set_parts.append("status = %s")
            params.append(status)
        if records_processed is not None:
            set_parts.append("records_processed = %s")
            params.append(records_processed)
        if records_inserted is not None:
            set_parts.append("records_inserted = %s")
            params.append(records_inserted)
        if records_updated is not None:
            set_parts.append("records_updated = %s")
            params.append(records_updated)
        if records_skipped is not None:
            set_parts.append("records_skipped = %s")
            params.append(records_skipped)
        if errors is not None:
            set_parts.append("errors = %s")
            params.append(errors)
        if finished_at is not None:
            set_parts.append("finished_at = %s")
            params.append(finished_at)
        if duration_seconds is not None:
            set_parts.append("duration_seconds = %s")
            params.append(duration_seconds)

        if not set_parts:
            return

        params.append(run_id)
        query = f"UPDATE import_runs SET {', '.join(set_parts)} WHERE id = %s"
        with self.conn.cursor() as cur:
            cur.execute(query, params)

    def get_by_provider(self, provider_id: str) -> list[dict]:
        """Get import runs for a provider."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, provider_id, pipeline, status, records_processed, records_inserted, "
                "records_updated, records_skipped, errors, started_at, finished_at, "
                "duration_seconds FROM import_runs WHERE provider_id = %s ORDER BY started_at DESC",
                (provider_id,)
            )
            return [dict(row) for row in cur.fetchall()]

    def get_latest(self, provider_id: str) -> dict | None:
        """Get the latest import run for a provider."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, provider_id, pipeline, status, records_processed, records_inserted, "
                "records_updated, records_skipped, errors, started_at, finished_at, "
                "duration_seconds FROM import_runs WHERE provider_id = %s ORDER BY started_at DESC LIMIT 1",
                (provider_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None