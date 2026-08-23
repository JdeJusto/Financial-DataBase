"""Company repository.

Handles all database operations for the companies table.
"""



class CompanyRepository:
    """Repository for companies table."""

    def __init__(self, conn):
        self.conn = conn

    def create(self, legal_name: str, country: str | None = None,
               sector: str | None = None, industry: str | None = None,
               currency: str | None = None, website: str | None = None) -> dict:
        """Insert a new company."""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO companies (legal_name, country, sector, industry, currency, website)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (legal_name) DO UPDATE
                   SET country = EXCLUDED.country,
                       sector = EXCLUDED.sector,
                       industry = EXCLUDED.industry,
                       currency = EXCLUDED.currency,
                       website = EXCLUDED.website,
                       updated_at = NOW()
                   RETURNING id, legal_name, country, sector, industry, currency, website, created_at, updated_at""",
                (legal_name, country, sector, industry, currency, website)
            )
            return dict(cur.fetchone())

    def get_by_id(self, company_id: str) -> dict | None:
        """Get company by internal ID."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, legal_name, country, sector, industry, currency, website, created_at, updated_at FROM companies WHERE id = %s",
                (company_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def list_all(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """List companies with pagination."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, legal_name, country, sector, industry, currency, website, created_at, updated_at FROM companies WHERE is_active = TRUE ORDER BY legal_name LIMIT %s OFFSET %s",
                (limit, offset)
            )
            return [dict(row) for row in cur.fetchall()]