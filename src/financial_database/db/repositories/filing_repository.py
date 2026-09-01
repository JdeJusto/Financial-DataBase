"""Filing repository.

Handles SEC and other provider filings.
"""

from typing import Any

import psycopg


class FilingRepository:
    """Repository for filings table."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def create(
        self,
        company_id: str,
        provider_id: str,
        form: str,
        accession_number: str,
        filing_date: str,
        period_start: str | None,
        period_end: str,
        fiscal_year: int | None = None,
        fiscal_period: str = "FY",
        filing_url: str | None = None,
        raw_document_id: str | None = None,
        is_amended: bool = False,
        amended_by_filing_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new filing."""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO filings (company_id, provider_id, form, accession_number, filing_date, period_start, period_end,
                   fiscal_year, fiscal_period, filing_url, raw_document_id, is_amended, amended_by_filing_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (provider_id, accession_number) DO NOTHING
                   RETURNING id, company_id, provider_id, form, accession_number, filing_date, period_start, period_end,
                   fiscal_year, fiscal_period, filing_url, raw_document_id, is_amended, amended_by_filing_id, created_at""",
                (
                    company_id,
                    provider_id,
                    form,
                    accession_number,
                    filing_date,
                    period_start,
                    period_end,
                    fiscal_year,
                    fiscal_period,
                    filing_url,
                    raw_document_id,
                    is_amended,
                    amended_by_filing_id,
                ),
            )
            rows = cur.fetchall(); return rows[0] if rows else None

    def get_by_company_id(self, company_id: str) -> list[dict]:
        """Get all filings for a company."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT f.id, f.company_id, f.provider_id, f.form, f.accession_number, f.filing_date, f.period_start, f.period_end, "
                "f.fiscal_year, f.fiscal_period, f.filing_url, f.raw_document_id, f.is_amended, f.amended_by_filing_id, f.created_at, "
                "c.legal_name "
                "FROM filings f JOIN companies c ON f.company_id = c.id WHERE f.company_id = %s ORDER BY f.filing_date DESC",
                (company_id,),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_by_accession(self, provider_id: str, accession_number: str) -> dict | None:
        """Get filing by provider accession ID."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT f.id, f.company_id, f.provider_id, f.form, f.accession_number, f.filing_date, f.period_start, f.period_end, "
                "f.fiscal_year, f.fiscal_period, f.filing_url, f.raw_document_id, f.is_amended, f.amended_by_filing_id, f.created_at, "
                "c.legal_name "
                "FROM filings f JOIN companies c ON f.company_id = c.id WHERE f.provider_id = %s AND f.accession_number = %s",
                (provider_id, accession_number),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def list_recent(self, limit: int = 50) -> list[dict]:
        """List most recent filings."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT f.id, f.company_id, f.provider_id, f.form, f.accession_number, f.filing_date, f.period_start, f.period_end, "
                "f.fiscal_year, f.fiscal_period, c.legal_name "
                "FROM filings f JOIN companies c ON f.company_id = c.id ORDER BY f.filing_date DESC LIMIT %s",
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]
