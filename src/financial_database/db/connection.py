"""Database connection module.

Provides PostgreSQL connection using psycopg3.
"""

import os

import psycopg
import psycopg.rows


def get_connection():
    """Get PostgreSQL connection from environment variables.

    Uses DATABASE_URL environment variable, or defaults to local development.
    Returns a connection with dict_row factory for easy row-to-dict conversion.
    """
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://financial:test@localhost:5432/financial_database"
    )
    return psycopg.connect(database_url, row_factory=psycopg.rows.dict_row)