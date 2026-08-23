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
                   RETURNING id, legal_name, country, sector, industry, currency, website, created_at, updated_at""",
                (legal_name, country, sector, industry, currency, website)
            )
            return cur.fetchone()

    def update(self, company_id: str, legal_name: str | None = None,
               country: str | None = None, sector: str | None = None,
               industry: str | None = None, currency: str | None = None,
               website: str | None = None) -> dict | None:
        """Update an existing company."""
        set_parts = []
        params = []
        if legal_name is not None:
            set_parts.append("legal_name = %s")
            params.append(legal_name)
        if country is not None:
            set_parts.append("country = %s")
            params.append(country)
        if sector is not None:
            set_parts.append("sector = %s")
            params.append(sector)
        if industry is not None:
            set_parts.append("industry = %s")
            params.append(industry)
        if currency is not None:
            set_parts.append("currency = %s")
            params.append(currency)
        if website is not None:
            set_parts.append("website = %s")
            params.append(website)
        if not set_parts:
            return None
        set_parts.append("updated_at = NOW()")
        params.append(company_id)
        with self.conn.cursor() as cur:
            cur.execute(
                f"UPDATE companies SET {', '.join(set_parts)} WHERE id = %s RETURNING id, legal_name, country, sector, industry, currency, website, created_at, updated_at",
                params
            )
            return cur.fetchone()

    def get_by_id(self, company_id: str) -> dict | None:
        """Get company by internal ID."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, legal_name, country, sector, industry, currency, website, created_at, updated_at FROM companies WHERE id = %s",
                (company_id,)
            )
            return cur.fetchone()

    def list_all(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """List companies with pagination."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, legal_name, country, sector, industry, currency, website, created_at, updated_at FROM companies WHERE is_active = TRUE ORDER BY legal_name LIMIT %s OFFSET %s",
                (limit, offset)
            )
            return cur.fetchall()