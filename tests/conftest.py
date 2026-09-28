"""Test fixtures for financial database tests."""

import asyncio
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Test database configuration - use environment or defaults
TEST_DB_NAME = os.environ.get("TEST_DB_NAME", "financial_database_test")
TEST_DB_USER = os.environ.get("TEST_DB_USER", "financial")
TEST_DB_PASSWORD = os.environ.get("TEST_DB_PASSWORD", "test")
TEST_DB_HOST = os.environ.get("TEST_DB_HOST", "localhost")
TEST_DB_PORT = os.environ.get("TEST_DB_PORT", "5432")


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_db_url():
    """Get test database URL."""
    return f"postgresql://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/{TEST_DB_NAME}"


@pytest.fixture(scope="session")
def db_engine(test_db_url):
    """Create a SQLAlchemy engine for the test database.

    The URL uses the psycopg3 dialect, matching the application's driver
    (``psycopg[binary]``), so the test environment no longer needs a second
    PostgreSQL driver installed.
    """
    connection_url = test_db_url.replace("postgresql://", "postgresql+psycopg://")
    engine = create_engine(connection_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Create a database session for testing."""
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def async_db_engine(test_db_url):
    """Create an async SQLAlchemy engine for the test database."""
    # Convert to asyncpg URL
    connection_url = test_db_url.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(connection_url)
    yield engine
    engine.dispose()


@pytest.fixture
def async_db_session(async_db_engine):
    """Create an async database session for testing."""

    async def _get_session():
        async with async_db_engine.connect() as conn:
            async_session = AsyncSession(bind=conn, expire_on_commit=False)
            yield async_session

    return _get_session()


@pytest.fixture
def db_connection(test_db_url):
    """Create a psycopg connection for testing repositories directly.

    Function-scoped so each test gets a fresh connection to the isolated test
    database and its transaction can be rolled back during teardown.
    """
    import psycopg
    from psycopg.rows import dict_row

    conn = psycopg.connect(
        test_db_url.replace("postgresql://", "postgresql://"), row_factory=dict_row
    )
    conn.autocommit = False

    # Add execute_script method for running SQL scripts with parameters
    def execute_script(script_path, params=None):
        """Execute a SQL script with optional parameters.

        Args:
            script_path: Path to the SQL script file
            params: Dictionary of parameters to substitute in the script

        Returns:
            List of dictionaries representing the query results
        """
        with open(script_path, 'r') as f:
            script_content = f.read()

        # Replace parameters in the script.
        # Scripts may use either psql-style (:key) or DBAPI-style
        # (%(key)s) named placeholders; support both.
        if params:
            for key, value in params.items():
                if isinstance(value, str):
                    # For string values, we need to quote them and escape single quotes
                    escaped_value = value.replace("'", "''")
                    quoted = f"'{escaped_value}'"
                    script_content = script_content.replace(f':{key}', quoted)
                    script_content = script_content.replace(f'%({key})s', quoted)
                elif isinstance(value, list):
                    # Handle array parameters (for IN clauses etc.)
                    if all(isinstance(item, str) for item in value):
                        quoted_items = ["'{}'".format(item.replace("'", "''")) for item in value]
                        array_str = "ARRAY[{}]".format(','.join(quoted_items))
                    else:
                        array_str = f"ARRAY[{','.join(str(item) for item in value)}]"
                    script_content = script_content.replace(f':{key}', array_str)
                    script_content = script_content.replace(f'%({key})s', array_str)
                else:
                    # For numeric values
                    script_content = script_content.replace(f':{key}', str(value))
                    script_content = script_content.replace(f'%({key})s', str(value))

        with conn.cursor() as cur:
            cur.execute(script_content)
            if cur.description:  # If it's a SELECT query
                columns = [desc[0] for desc in cur.description]
                results = []
                for row in cur.fetchall():
                    # With dict_row factory, row is already a dict-like object
                    # Convert it to a proper dict
                    if hasattr(row, 'keys'):
                        results.append(dict(row))
                    else:
                        results.append(dict(zip(columns, row)))
                return results
            else:
                # For non-SELECT queries, return empty list
                return []

    # Attach the method to the connection object
    conn.execute_script = execute_script

    yield conn
    conn.rollback()
    conn.close()
