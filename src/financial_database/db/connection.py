"""Database connection module.

Provides PostgreSQL connection using psycopg3.

"""

import os
from typing import Any

import psycopg
import psycopg.rows
from psycopg.rows import dict_row


def get_connection() -> psycopg.Connection[Any]:
    """Get PostgreSQL connection from environment variables.

    Uses DATABASE_URL environment variable, or defaults to local development.
    Returns a connection with dict_row factory for easy row-to-dict conversion.
    """
    database_url = os.environ.get(
        "DATABASE_URL", "postgresql://financial:test@localhost:5432/financial_database"
    )
    return psycopg.connect(database_url, row_factory=dict_row)
