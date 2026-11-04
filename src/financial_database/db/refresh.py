"""Refresh the normalized materialized views after an ingest run."""

from __future__ import annotations


def refresh_core_financials(conn) -> None:
    """Refresh ``core_financials`` without blocking readers.

    Called once at the end of a batch ingest (not per company: the refresh
    scans ~5M facts and takes ~20 s). Requires the unique index created by
    migration 0022.
    """
    with conn.cursor() as cur:
        cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY core_financials")
    conn.commit()
