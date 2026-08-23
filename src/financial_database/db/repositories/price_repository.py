"""Price repository.

Handles historical prices per listing per provider.
Uses NUMERIC type for precision, not FLOAT.
"""


class PriceRepository:
    """Repository for prices table."""

    def __init__(self, conn):
        self.conn = conn

    def create(
        self,
        listing_id: str,
        price_date: str,
        open_price,
        high,
        low,
        close,
        adjusted_close,
        volume: int,
        currency: str = "USD",
        provider_id: str = "",
        source_id: str = "",
    ) -> dict:
        """Insert a new price observation."""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO prices (listing_id, price_date, open, high, low, close, adjusted_close,
                   volume, currency, provider_id, source_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (listing_id, price_date, provider_id) DO NOTHING
                   RETURNING id, listing_id, price_date, open, high, low, close, adjusted_close,
                   volume, currency, provider_id, source_id, created_at""",
                (
                    listing_id,
                    price_date,
                    float(open_price) if open_price else None,
                    float(high) if high else None,
                    float(low) if low else None,
                    float(close) if close else None,
                    float(adjusted_close) if adjusted_close else None,
                    int(volume) if volume else None,
                    currency,
                    provider_id,
                    source_id,
                ),
            )
            return cur.fetchone()

    def get_by_listing_id(self, listing_id: str) -> list[dict]:
        """Get all prices for a listing."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, listing_id, price_date, open, high, low, close, adjusted_close, "
                "volume, currency, provider_id, source_id, created_at "
                "FROM prices WHERE listing_id = %s ORDER BY price_date DESC",
                (listing_id,),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_by_listing_date(self, listing_id: str, price_date: str) -> dict | None:
        """Get price for a specific listing and date."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, listing_id, price_date, open, high, low, close, adjusted_close, "
                "volume, currency, provider_id, source_id, created_at "
                "FROM prices WHERE listing_id = %s AND price_date = %s",
                (listing_id, price_date),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_latest_by_listing(self, listing_id: str) -> dict | None:
        """Get the latest price for a listing."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, listing_id, price_date, open, high, low, close, adjusted_close, "
                "volume, currency, provider_id, source_id, created_at "
                "FROM prices WHERE listing_id = %s ORDER BY price_date DESC LIMIT 1",
                (listing_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_range_by_listing(
        self, listing_id: str, start_date: str, end_date: str
    ) -> list[dict]:
        """Get prices within a date range for a listing."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, listing_id, price_date, open, high, low, close, adjusted_close, "
                "volume, currency, provider_id, source_id, created_at "
                "FROM prices WHERE listing_id = %s AND price_date BETWEEN %s AND %s ORDER BY price_date",
                (listing_id, start_date, end_date),
            )
            return [dict(row) for row in cur.fetchall()]
