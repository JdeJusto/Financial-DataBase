"""Unit tests for exchanges table functionality."""

import pytest
from sqlalchemy import text


def test_exchanges_table_structure(db_session):
    """Test that exchanges table has correct structure."""
    # Check table exists
    result = db_session.execute(text("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'exchanges'
        ORDER BY ordinal_position
    """))
    columns = result.fetchall()
    
    # Convert to dict for easier checking
    column_dict = {row[0]: {"type": row[1], "nullable": row[2], "default": row[3]} for row in columns}
    
    # Check required columns exist
    assert "id" in column_dict
    assert column_dict["id"]["type"] == "uuid"
    assert column_dict["id"]["nullable"] == "NO"
    
    assert "code" in column_dict
    assert column_dict["code"]["type"] == "character varying"
    assert column_dict["code"]["nullable"] == "NO"
    
    assert "name" in column_dict
    assert column_dict["name"]["type"] == "character varying"
    assert column_dict["name"]["nullable"] == "NO"
    
    assert "country" in column_dict
    assert column_dict["country"]["type"] == "character varying"
    assert column_dict["country"]["nullable"] == "YES"
    
    assert "timezone" in column_dict
    assert column_dict["timezone"]["type"] == "character varying"
    assert column_dict["timezone"]["nullable"] == "YES"
    
    assert "currency" in column_dict
    assert column_dict["currency"]["type"] == "character varying"
    assert column_dict["currency"]["nullable"] == "YES"
    assert column_dict["currency"]["default"] == "'USD'::character varying"
    
    assert "is_active" in column_dict
    assert column_dict["is_active"]["type"] == "boolean"
    assert column_dict["is_active"]["nullable"] == "YES"
    assert column_dict["is_active"]["default"] == "true"
    
    assert "created_at" in column_dict
    assert column_dict["created_at"]["type"] == "timestamp with time zone"
    assert column_dict["created_at"]["nullable"] == "NO"
    assert "now()" in column_dict["created_at"]["default"]
    
    assert "updated_at" in column_dict
    assert column_dict["updated_at"]["type"] == "timestamp with time zone"
    assert column_dict["updated_at"]["nullable"] == "NO"
    assert "now()" in column_dict["updated_at"]["default"]


def test_exchanges_table_constraints(db_session):
    """Test that exchanges table has correct constraints."""
    # Check primary key
    result = db_session.execute(text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'exchanges' AND constraint_type = 'PRIMARY KEY'
    """))
    pk_constraint = result.fetchone()
    assert pk_constraint is not None
    assert pk_constraint[0] == "exchanges_pkey"
    
    # Check unique constraint on code
    result = db_session.execute(text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'exchanges' AND constraint_type = 'UNIQUE'
    """))
    unique_constraints = result.fetchall()
    assert len(unique_constraints) >= 1
    constraint_names = [c[0] for c in unique_constraints]
    assert any("code" in c.lower() for c in constraint_names)


def test_insert_exchange(db_session):
    """Test inserting an exchange record."""
    insert_sql = """
        INSERT INTO exchanges (code, name, country, timezone, currency, is_active)
        VALUES (:code, :name, :country, :timezone, :currency, :is_active)
        RETURNING id
    """

    result = db_session.execute(text(insert_sql), {
        "code": "NASDAQ",
        "name": "National Association of Securities Dealers Automated Quotations",
        "country": "USA",
        "timezone": "America/New_York",
        "currency": "USD",
        "is_active": True
    })

    exchange_id = result.fetchone()[0]
    db_session.commit()

    # Verify the exchange was inserted correctly
    select_sql = """
        SELECT code, name, country, timezone, currency, is_active
        FROM exchanges WHERE id = :exchange_id
    """

    result = db_session.execute(text(select_sql), {
        "exchange_id": exchange_id
    })
    exchange = result.fetchone()

    assert exchange is not None
    assert exchange[0] == "NASDAQ"
    assert exchange[1] == "National Association of Securities Dealers Automated Quotations"
    assert exchange[2] == "USA"
    assert exchange[3] == "America/New_York"
    assert exchange[4] == "USD"
    assert exchange[5] is True
