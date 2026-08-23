"""Dividend repository.

Handles dividend payments per listing per provider.
"""


class DividendRepository:
    """Repository for dividends table."""

    def __init__(self, conn):
        self.conn = conn

    def create(
        self,
        listing_id: str,
        ex_dividend_date: str | None = None,
        record_date: str | None = None,
        payment_date: str | None = None,
        amount: float | None = None,
        currency: str = "USD",
        provider_id: str = "",
        source_id: str = "",
    ) -> dict:
        """Create a new dividend record."""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO dividends (listing_id, ex_dividend_date, record_date, payment_date,
                   amount, currency, provider_id, source_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (listing_id, ex_dividend_date, provider_id, source_id) DO NOTHING
                   RETURNING id, listing_id, ex_dividend_date, record_date, payment_date,
                   amount, currency, provider_id, source_id, created_at""",
                (
                    listing_id,
                    ex_dividend_date,
                    record_date,
                    payment_date,
                    float(amount) if amount else None,
                    currency,
                    provider_id,
                    source_id,
                ),
            )
            return cur.fetchone()

    def get_by_listing_id(self, listing_id: str) -> list[dict]:
        """Get all dividends for a listing."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, listing_id, ex_dividend_date, record_date, payment_date, "
                "amount, currency, provider_id, source_id, created_at "
                "FROM dividends WHERE listing_id = %s ORDER BY ex_dividend_date DESC",
                (listing_id,),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_by_date_range(
        self, listing_id: str, start_date: str, end_date: str
    ) -> list[dict]:
        """Get dividends within a date range."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, listing_id, ex_dividend_date, record_date, payment_date, "
                "amount, currency, provider_id, source_id, created_at "
                "FROM dividends WHERE listing_id = %s AND ex_dividend_date BETWEEN %s AND %s ORDER BY ex_dividend_date",
                (listing_id, start_date, end_date),
            )
            return [dict(row) for row in cur.fetchall()]
