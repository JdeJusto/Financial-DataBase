"""Data provider repository.

Handles all database operations for the data_providers table.
"""

from typing import Any

import psycopg
from psycopg.rows import dict_row


class DataProviderRepository:
    """Repository for data_providers table."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def get_by_name(self, name: str) -> dict[str, Any] | None:
        """Get a data provider by name."""
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, name, type, display_name, base_url, is_active, created_at, updated_at
                FROM data_providers
                WHERE name = %s
                """,
                (name,),
            )
            return cur.fetchone()

    def create(self, provider_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new data provider."""
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO data_providers (name, type, display_name, base_url, is_active)
                VALUES (%(name)s, %(type)s, %(display_name)s, %(base_url)s, %(is_active)s)
                RETURNING id, name, type, display_name, base_url, is_active, created_at, updated_at
                """,
                provider_data,
            )
            return cur.fetchone()
