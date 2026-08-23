"""Financial fact repository.

The most important table - normalized financial facts
with full provenance and restatement support.
"""



class FinancialFactRepository:
    """Repository for financial_facts table."""

    def __init__(self, conn):
        self.conn = conn

    def create(self, company_id: str, concept: str, value, unit: str,
               period_start: str | None, period_end: str,
               fiscal_year: int, fiscal_period: str,
               provider_id: str, source_id: str | None = None,
               filing_id: str | None = None,
               form: str | None = None,
               filing_date: str | None = None) -> dict:
        """Insert a new financial fact."""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO financial_facts (company_id, concept, value, unit, period_start, period_end,
                   fiscal_year, fiscal_period, provider_id, source_id, filing_id, form, filing_date)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (company_id, concept, period_start, period_end, filing_id, source_id) DO NOTHING
                   RETURNING id, company_id, concept, value, unit, period_start, period_end,
                   fiscal_year, fiscal_period, provider_id, source_id, filing_id, form, filing_date, created_at""",
                (company_id, concept, float(value) if value else None, unit,
                 period_start, period_end, fiscal_year, fiscal_period, provider_id,
                 source_id, filing_id, form, filing_date)
            )
            return cur.fetchone()

    def get_by_company_id(self, company_id: str) -> list[dict]:
        """Get all financial facts for a company."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT ff.id, ff.company_id, ff.concept, ff.value, ff.unit, ff.period_start, ff.period_end, "
                "ff.fiscal_year, ff.fiscal_period, ff.provider_id, ff.source_id, ff.filing_id, ff.form, ff.filing_date, "
                "ff.created_at, c.legal_name "
                "FROM financial_facts ff JOIN companies c ON ff.company_id = c.id WHERE ff.company_id = %s ORDER BY ff.fiscal_year DESC, ff.period_end DESC",
                (company_id,)
            )
            return [dict(row) for row in cur.fetchall()]

    def get_by_concept(self, company_id: str, concept: str) -> list[dict]:
        """Get all observations of a specific concept for a company."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT ff.id, ff.company_id, ff.concept, ff.value, ff.unit, ff.period_start, ff.period_end, "
                "ff.fiscal_year, ff.fiscal_period, ff.provider_id, ff.source_id, ff.filing_id, ff.form, ff.filing_date, "
                "ff.created_at, c.legal_name "
                "FROM financial_facts ff JOIN companies c ON ff.company_id = c.id "
                "WHERE ff.concept = %s AND ff.company_id = %s ORDER BY ff.fiscal_year DESC, ff.period_end DESC",
                (concept, company_id)
            )
            return [dict(row) for row in cur.fetchall()]

    def get_latest_by_concept(self, company_id: str, concept: str) -> dict | None:
        """Get the latest observation of a concept for a company."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT ff.id, ff.company_id, ff.concept, ff.value, ff.unit, ff.period_start, ff.period_end, "
                "ff.fiscal_year, ff.fiscal_period, ff.provider_id, ff.source_id, ff.filing_id, ff.form, ff.filing_date, "
                "ff.created_at, c.legal_name "
                "FROM financial_facts ff JOIN companies c ON ff.company_id = c.id "
                "WHERE ff.concept = %s AND ff.company_id = %s ORDER BY ff.filing_date DESC LIMIT 1",
                (concept, company_id)
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_instant_facts(self, company_id: str, concept: str | None = None) -> list[dict]:
        """Get instant (balance sheet) facts where period_start IS NULL."""
        with self.conn.cursor() as cur:
            if concept:
                cur.execute(
                    "SELECT ff.id, ff.company_id, ff.concept, ff.value, ff.unit, ff.period_start, ff.period_end, "
                    "ff.fiscal_year, ff.fiscal_period, ff.provider_id, ff.source_id, ff.filing_id, ff.form, ff.filing_date, "
                    "ff.created_at, c.legal_name "
                    "FROM financial_facts ff JOIN companies c ON ff.company_id = c.id "
                    "WHERE ff.concept = %s AND ff.company_id = %s AND ff.period_start IS NULL "
                    "ORDER BY ff.filing_date DESC",
                    (concept, company_id)
                )
            else:
                cur.execute(
                    "SELECT ff.id, ff.company_id, ff.concept, ff.value, ff.unit, ff.period_start, ff.period_end, "
                    "ff.fiscal_year, ff.fiscal_period, ff.provider_id, ff.source_id, ff.filing_id, ff.form, ff.filing_date, "
                    "ff.created_at, c.legal_name "
                    "FROM financial_facts ff JOIN companies c ON ff.company_id = c.id "
                    "WHERE ff.company_id = %s AND ff.period_start IS NULL "
                    "ORDER BY ff.filing_date DESC",
                    (company_id,)
                )
            return [dict(row) for row in cur.fetchall()]

    def get_duration_facts(self, company_id: str, concept: str | None = None) -> list[dict]:
        """Get duration (income statement) facts where period_start IS NOT NULL."""
        with self.conn.cursor() as cur:
            if concept:
                cur.execute(
                    "SELECT ff.id, ff.company_id, ff.concept, ff.value, ff.unit, ff.period_start, ff.period_end, "
                    "ff.fiscal_year, ff.fiscal_period, ff.provider_id, ff.source_id, ff.filing_id, ff.form, ff.filing_date, "
                    "ff.created_at, c.legal_name "
                    "FROM financial_facts ff JOIN companies c ON ff.company_id = c.id "
                    "WHERE ff.concept = %s AND ff.company_id = %s AND ff.period_start IS NOT NULL "
                    "ORDER BY ff.filing_date DESC",
                    (concept, company_id)
                )
            else:
                cur.execute(
                    "SELECT ff.id, ff.company_id, ff.concept, ff.value, ff.unit, ff.period_start, ff.period_end, "
                    "ff.fiscal_year, ff.fiscal_period, ff.provider_id, ff.source_id, ff.filing_id, ff.form, ff.filing_date, "
                    "ff.created_at, c.legal_name "
                    "FROM financial_facts ff JOIN companies c ON ff.company_id = c.id "
                    "WHERE ff.company_id = %s AND ff.period_start IS NOT NULL "
                    "ORDER BY ff.filing_date DESC",
                    (company_id,)
                )
            return [dict(row) for row in cur.fetchall()]