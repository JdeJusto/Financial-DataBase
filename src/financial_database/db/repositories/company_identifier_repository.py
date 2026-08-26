"""Company identifier repository.

Handles ticker, CIK, ISIN, LEI and provider-specific identifiers.
"""

import psycopg
from typing import Any


class CompanyIdentifierRepository:
    """Repository for company_identifiers table."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def create(
        self,
        company_id: str,
        identifier_type: str,
        identifier_value: str,
        provider_id: str | None = None,
        is_primary: bool = False,
        valid_from: str | None = None,
        valid_to: str | None = None,
    ) -> dict[str, Any]:
        """Insert a new identifier."""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO company_identifiers (company_id, identifier_type, identifier_value, provider_id, is_primary, valid_from, valid_to)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (company_id, identifier_type, provider_id, identifier_value) DO NOTHING
                   RETURNING id, company_id, identifier_type, identifier_value, provider_id, is_primary, valid_from, valid_to, created_at""",
                (
                    company_id,
                    identifier_type,
                    identifier_value,
                    provider_id,
                    is_primary,
                    valid_from,
                    valid_to,
                ),
            )
            return cur.fetchone()

    def get_by_company_id(self, company_id: str) -> list[dict]:
        """Get all identifiers for a company."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, company_id, identifier_type, identifier_value, provider_id, is_primary, valid_from, valid_to, created_at FROM company_identifiers WHERE company_id = %s",
                (company_id,),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_by_value_and_type(
        self,
        identifier_value: str,
        identifier_type: str,
        provider_id: str | None = None,
    ) -> list[dict]:
        """Get identifiers by value and type."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, company_id, identifier_type, identifier_value, provider_id, is_primary, valid_from, valid_to, created_at FROM company_identifiers WHERE identifier_type = %s AND identifier_value = %s AND provider_id = %s",
                (identifier_type, identifier_value, provider_id),
            )
            return [dict(row) for row in cur.fetchall()]

    def set_primary(self, identifier_id: str) -> None:
        """Set an identifier as primary."""
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE company_identifiers SET is_primary = TRUE WHERE id = %s",
                (identifier_id,),
            )
