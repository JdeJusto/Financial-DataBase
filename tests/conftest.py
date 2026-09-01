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
    """Create a SQLAlchemy engine for the test database."""
    # Convert to psycopg2 URL
    connection_url = test_db_url.replace("postgresql://", "postgresql+psycopg2://")
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


@pytest.fixture(scope="session")
def db_connection(test_db_url):
    """Create a psycopg connection for testing repositories directly."""
    import psycopg
    from psycopg.rows import dict_row
    conn = psycopg.connect(test_db_url.replace("postgresql://", "postgresql://"), row_factory=dict_row)
    conn.autocommit = False
    yield conn
    conn.rollback()
    conn.close()
