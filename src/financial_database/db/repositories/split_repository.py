"""Split repository.

Handles stock splits per listing per provider.
"""


class SplitRepository:
    """Repository for splits table."""

    def __init__(self, conn):
        self.conn = conn

    def create(
        self,
        listing_id: str,
        execution_date: str,
        numerator: int,
        denominator: int,
        provider_id: str = "",
        source_id: str = "",
    ) -> dict:
        """Create a new stock split record."""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO splits (listing_id, execution_date, numerator, denominator,
                   provider_id, source_id)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (listing_id, execution_date, provider_id, source_id) DO NOTHING
                   RETURNING id, listing_id, execution_date, numerator, denominator,
                   provider_id, source_id, created_at""",
                (
                    listing_id,
                    execution_date,
                    numerator,
                    denominator,
                    provider_id,
                    source_id,
                ),
            )
            rows = cur.fetchall()
            return rows[0] if rows else None

    def get_by_listing_id(self, listing_id: str) -> list[dict]:
        """Get all splits for a listing."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, listing_id, execution_date, numerator, denominator, "
                "provider_id, source_id, created_at "
                "FROM splits WHERE listing_id = %s ORDER BY execution_date DESC",
                (listing_id,),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_by_date_range(
        self, listing_id: str, start_date: str, end_date: str
    ) -> list[dict]:
        """Get splits within a date range."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, listing_id, execution_date, numerator, denominator, "
                "provider_id, source_id, created_at "
                "FROM splits WHERE listing_id = %s AND execution_date BETWEEN %s AND %s ORDER BY execution_date",
                (listing_id, start_date, end_date),
            )
            return [dict(row) for row in cur.fetchall()]
