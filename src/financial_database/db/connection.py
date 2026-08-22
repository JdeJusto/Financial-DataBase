"""Database connection module.

Provides PostgreSQL connection using psycopg3.
"""

import os

import psycopg


def get_connection():
    """Get PostgreSQL connection from environment variables.

    Uses DATABASE_URL environment variable, or defaults to local development.
    """
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://financial:test@localhost:5432/financial_database"
    )
    return psycopg.connect(database_url)