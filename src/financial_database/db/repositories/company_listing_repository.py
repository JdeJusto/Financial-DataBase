"""Company listing repository.

Connects company + exchange + ticker with historical validity.
"""

from typing import Any

import psycopg


class CompanyListingRepository:
    """Repository for company_listings table."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def create(
        self,
        company_id: str,
        exchange_id: str,
        ticker: str,
        share_class: str | None = None,
        listing_date: str | None = None,
        delisting_date: str | None = None,
        is_primary: bool = False,
    ) -> dict[str, Any]:
        """Create a new company listing."""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO company_listings (company_id, exchange_id, ticker, share_class, listing_date, delisting_date, is_primary)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (company_id, exchange_id, share_class, listing_date) DO NOTHING
                   RETURNING id, company_id, exchange_id, ticker, share_class, listing_date, delisting_date, is_primary, created_at, updated_at""",
                (
                    company_id,
                    exchange_id,
                    ticker,
                    share_class,
                    listing_date,
                    delisting_date,
                    is_primary,
                ),
            )
            rows = cur.fetchall()
            return rows[0] if rows else None

    def get_by_company_id(self, company_id: str) -> list[dict]:
        """Get all listings for a company."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT cl.id, cl.company_id, cl.exchange_id, cl.ticker, cl.share_class, cl.listing_date, cl.delisting_date, cl.is_primary, "
                "e.code, e.name, e.country, e.timezone, e.currency "
                "FROM company_listings cl JOIN exchanges e ON cl.exchange_id = e.id WHERE cl.company_id = %s",
                (company_id,),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_by_ticker(self, ticker: str) -> list[dict]:
        """Get all listings with a specific ticker."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT cl.id, cl.company_id, cl.exchange_id, cl.ticker, cl.share_class, cl.listing_date, cl.delisting_date, cl.is_primary, "
                "e.code, e.name, e.country, e.timezone, e.currency "
                "FROM company_listings cl JOIN exchanges e ON cl.exchange_id = e.id WHERE cl.ticker = %s",
                (ticker,),
            )
            return [dict(row) for row in cur.fetchall()]

    def is_active_listing(self, listing_id: str) -> bool:
        """Check if a listing is active (not delisted)."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT is_active FROM company_listings WHERE id = %s", (listing_id,)
            )
            row = cur.fetchone()
            return row["is_active"] if row else False
