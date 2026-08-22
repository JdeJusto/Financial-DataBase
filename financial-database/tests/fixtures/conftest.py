"""Test fixtures for financial database tests."""

import os
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

# Test database configuration
TEST_DB_NAME = "financial_database_test"
TEST_DB_USER = "financial"
TEST_DB_PASSWORD = "test"
TEST_DB_HOST = "localhost"
TEST_DB_PORT = 5432


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def postgres_container():
    """Start a PostgreSQL container for testing."""
    with PostgresContainer(
        image="postgres:18",
        database=TEST_DB_NAME,
        username=TEST_DB_USER,
        password=TEST_DB_PASSWORD,
    ) as postgres:
        yield postgres


@pytest.fixture
def db_engine(postgres_container):
    """Create a SQLAlchemy engine for the test database."""
    connection_url = postgres_container.get_connection_url()
    engine = create_engine(connection_url.replace("postgresql://", "postgresql+psycopg2://"))
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
def async_db_engine(postgres_container):
    """Create an async SQLAlchemy engine for the test database."""
    connection_url = postgres_container.get_connection_url()
    engine = create_async_engine(connection_url.replace("postgresql://", "postgresql+asyncpg://"))
    yield engine
    engine.dispose()


@pytest.fixture
async def async_db_session(async_db_engine):
    """Create an async database session for testing."""
    async with async_db_engine.begin() as conn:
        async_session = AsyncSession(
            async_db_engine, expire_on_commit=False, bind=conn
        )
        yield async_session
