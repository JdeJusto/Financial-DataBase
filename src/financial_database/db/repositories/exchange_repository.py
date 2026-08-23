"""Exchange repository.

Handles exchanges where companies list.
"""


class ExchangeRepository:
    """Repository for exchanges table."""

    def __init__(self, conn):
        self.conn = conn

    def create(
        self,
        code: str,
        name: str,
        country: str | None = None,
        timezone: str | None = None,
        currency: str | None = None,
    ) -> dict:
        """Create a new exchange."""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO exchanges (code, name, country, timezone, currency)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (code) DO NOTHING
                   RETURNING id, code, name, country, timezone, currency, created_at""",
                (code, name, country, timezone, currency),
            )
            return cur.fetchone()

    def get_by_code(self, code: str) -> dict | None:
        """Get exchange by code (ticker prefix like NASDAQ, NYSE)."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, code, name, country, timezone, currency, created_at FROM exchanges WHERE code = %s",
                (code,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def list_all(self) -> list[dict]:
        """List all exchanges."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, code, name, country, timezone, currency, created_at, updated_at FROM exchanges WHERE is_active = TRUE ORDER BY name"
            )
            return [dict(row) for row in cur.fetchall()]
