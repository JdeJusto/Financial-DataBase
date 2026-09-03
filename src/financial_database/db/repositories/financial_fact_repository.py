"""Financial fact repository.

The most important table - normalized financial facts
with full provenance and restatement support.
"""

from typing import Any

import psycopg


class FinancialFactRepository:
    """Repository for financial_facts table."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def create(
        self,
        company_id: str,
        concept: str,
        value: Any,
        unit: str,
        period_start: str | None,
        period_end: str,
        fiscal_year: int,
        fiscal_period: str,
        provider_id: str,
        source_id: str | None = None,
        filing_id: str | None = None,
        form: str | None = None,
        filing_date: str | None = None,
        namespace: str | None = None,
        frame: str | None = None,
    ) -> dict[str, Any]:
        """Insert a new financial fact."""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO financial_facts (company_id, concept, namespace, value, unit, period_start, period_end,
                   fiscal_year, fiscal_period, provider_id, source_id, filing_id, form, filing_date, frame)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (company_id, concept, period_start, period_end, filing_id, source_id) DO NOTHING
                   RETURNING id, company_id, concept, namespace, value, unit, period_start, period_end,
                   fiscal_year, fiscal_period, provider_id, source_id, filing_id, form, filing_date, frame, created_at""",
                (
                    company_id,
                    concept,
                    namespace,
                    value,
                    unit,
                    period_start,
                    period_end,
                    fiscal_year,
                    fiscal_period,
                    provider_id,
                    source_id,
                    filing_id,
                    form,
                    filing_date,
                    frame,
                ),
            )
            rows = cur.fetchall()
            return rows[0] if rows else None

    def get_by_company_id(self, company_id: str) -> list[dict[str, Any]]:
        """Get all financial facts for a company."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT ff.id, ff.company_id, ff.concept, ff.value, ff.unit, ff.period_start, ff.period_end, "
                "ff.fiscal_year, ff.fiscal_period, ff.provider_id, ff.source_id, ff.filing_id, ff.form, ff.filing_date, "
                "ff.created_at, c.legal_name "
                "FROM financial_facts ff JOIN companies c ON ff.company_id = c.id WHERE ff.company_id = %s ORDER BY ff.fiscal_year DESC, ff.period_end DESC",
                (company_id,),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_by_concept(self, company_id: str, concept: str) -> list[dict[str, Any]]:
        """Get all observations of a specific concept for a company."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT ff.id, ff.company_id, ff.concept, ff.value, ff.unit, ff.period_start, ff.period_end, "
                "ff.fiscal_year, ff.fiscal_period, ff.provider_id, ff.source_id, ff.filing_id, ff.form, ff.filing_date, "
                "ff.created_at, c.legal_name "
                "FROM financial_facts ff JOIN companies c ON ff.company_id = c.id "
                "WHERE ff.concept = %s AND ff.company_id = %s ORDER BY ff.fiscal_year DESC, ff.period_end DESC",
                (concept, company_id),
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
                (concept, company_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_instant_facts(
        self, company_id: str, concept: str | None = None
    ) -> list[dict]:
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
                    (concept, company_id),
                )
            else:
                cur.execute(
                    "SELECT ff.id, ff.company_id, ff.concept, ff.value, ff.unit, ff.period_start, ff.period_end, "
                    "ff.fiscal_year, ff.fiscal_period, ff.provider_id, ff.source_id, ff.filing_id, ff.form, ff.filing_date, "
                    "ff.created_at, c.legal_name "
                    "FROM financial_facts ff JOIN companies c ON ff.company_id = c.id "
                    "WHERE ff.company_id = %s AND ff.period_start IS NULL "
                    "ORDER BY ff.filing_date DESC",
                    (company_id,),
                )

    def create_batch(
        self,
        facts: list[dict],
    ) -> list[dict]:
        """Insert multiple financial facts in a single batch.

        Each fact dict should contain all fields required by create().
        Returns list of inserted facts (excludes duplicates skipped by ON CONFLICT).
        """
        if not facts:
            return []

        with self.conn.cursor() as cur:
            # Build multi-row INSERT
            placeholders = ", ".join(["%s"] * 15)
            rows_placeholder = f"({placeholders})"
            rows_placeholders = ", ".join([rows_placeholder] * len(facts))

            query = f"""INSERT INTO financial_facts (company_id, concept, namespace, value, unit, period_start, period_end,
               fiscal_year, fiscal_period, provider_id, source_id, filing_id, form, filing_date, frame)
               VALUES {rows_placeholders}
               ON CONFLICT (company_id, concept, period_start, period_end, filing_id, source_id) DO NOTHING
               RETURNING id, company_id, concept, namespace, value, unit, period_start, period_end,
               fiscal_year, fiscal_period, provider_id, source_id, filing_id, form, filing_date, frame, created_at"""

            # Flatten facts into single parameter list
            params = []
            for fact in facts:
                params.extend(
                    [
                        fact["company_id"],
                        fact["concept"],
                        fact.get("namespace"),
                        fact["value"],
                        fact["unit"],
                        fact.get("period_start"),
                        fact["period_end"],
                        fact["fiscal_year"],
                        fact["fiscal_period"],
                        fact["provider_id"],
                        fact.get("source_id"),
                        fact.get("filing_id"),
                        fact.get("form"),
                        fact.get("filing_date"),
                        fact.get("frame"),
                    ]
                )

            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
