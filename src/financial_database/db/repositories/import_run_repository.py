"""Import run repository.

Audit metadata for import pipelines.
Tracks provenance of data loading operations.
"""

from typing import Any

import psycopg


class ImportRunRepository:
    """Repository for import_runs table."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def create(
        self, provider_id: str, pipeline: str, status: str = "running"
    ) -> dict[str, Any]:
        """Create a new import run record."""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO import_runs (provider_id, pipeline, status)
                   VALUES (%s, %s, %s)
                   RETURNING id, provider_id, pipeline, status, records_processed, records_inserted,
                   records_updated, records_skipped, errors, started_at, finished_at,
                   duration_seconds""",
                (provider_id, pipeline, status),
            )
            rows = cur.fetchall()
            return rows[0] if rows else None

    def update(
        self,
        run_id: str,
        status: str | None = None,
        records_processed: int | None = None,
        records_inserted: int | None = None,
        records_updated: int | None = None,
        records_skipped: int | None = None,
        errors: dict[str, Any] | None = None,
        finished_at=None,
        duration_seconds: int | None = None,
    ) -> None:
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
            import json

            params.append(json.dumps(errors))
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
                (provider_id,),
            )
            return [dict(row) for row in cur.fetchall()]

    def mark_dangling_running(
        self, provider_id: str, pipelines: list[str] | None = None
    ) -> int:
        """Close import runs still stuck in 'running' state.

        A crashed or killed process leaves its import_run in 'running' forever,
        which dashboards/health checks read as a phantom active pipeline. This
        flags those dangling rows as 'failed' (the schema CHECK constraint only
        permits 'running'/'success'/'failed'/'partial' — 'interrupted' would
        require a migration, out of scope) and stamps finished_at, recording an
        interruption note in the JSONB errors field. When ``pipelines`` is
        given, only runs of those pipelines are closed; otherwise every running
        run of the provider is closed. Returns the number of runs updated.

        This is the *pre-run* hook: it reconciles immediately, before a new run
        of the same pipelines starts. For age-based cleanup of any pipeline
        (``prices_update`` included) use :meth:`close_dangling_runs`.
        """
        pipeline_filter = ""
        params: tuple[Any, ...] = (provider_id,)
        if pipelines:
            pipeline_filter = " AND pipeline = ANY(%s)"
            params += (pipelines,)
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE import_runs "
                "SET status = 'failed', "
                "finished_at = NOW(), "
                "duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::int, "
                "errors = COALESCE(errors, '{}'::jsonb) "
                '|| \'{"reason": "interrupted: previous run left dangling"}\'::jsonb '
                "WHERE provider_id = %s AND status = 'running'" + pipeline_filter,
                params,
            )
            return cur.rowcount or 0

    def close_dangling_runs(
        self,
        max_age_hours: float = 6.0,
        pipelines: list[str] | None = None,
    ) -> list[dict]:
        """Close import runs stuck in 'running' for longer than ``max_age_hours``.

        Age-based maintenance cleanup for **any** pipeline (``prices_update``
        included, not just the SEC ones): a killed or crashed process never
        gets to close its own row, and a phantom 'running' run misleads
        dashboards, health checks and freshness queries. Rows younger than the
        threshold are left alone so a legitimately long run is never killed.

        Existing error context is preserved (the reason is merged into the
        JSONB ``errors`` column, never overwritten) and the previous age is
        recorded with it, so the closure is auditable.

        Returns the closed rows (``id``, ``pipeline``, ``started_at``,
        ``age_hours``) for logging.
        """
        params: tuple[Any, ...] = (max_age_hours,)
        pipeline_filter = ""
        if pipelines:
            pipeline_filter = " AND pipeline = ANY(%s)"
            params += (pipelines,)
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE import_runs "
                "SET status = 'failed', "
                "finished_at = NOW(), "
                "duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::int, "
                "errors = COALESCE(errors, '{}'::jsonb) || jsonb_build_object("
                "'reason', 'stale_running_closed_by_maintenance', "
                "'previous_status', 'running', "
                "'age_hours', ROUND("
                "(EXTRACT(EPOCH FROM (NOW() - started_at)) / 3600)::numeric, 2)"
                ") "
                "WHERE status = 'running' "
                "AND started_at < NOW() - (%s * interval '1 hour')"
                + pipeline_filter
                + " RETURNING id, pipeline, started_at, ROUND("
                "(EXTRACT(EPOCH FROM (NOW() - started_at)) / 3600)::numeric, 2)"
                " AS age_hours",
                params,
            )
            return [dict(row) for row in cur.fetchall()]

    def get_latest(self, provider_id: str) -> dict | None:
        """Get the latest import run for a provider."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, provider_id, pipeline, status, records_processed, records_inserted, "
                "records_updated, records_skipped, errors, started_at, finished_at, "
                "duration_seconds FROM import_runs WHERE provider_id = %s ORDER BY started_at DESC LIMIT 1",
                (provider_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
