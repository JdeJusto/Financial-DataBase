"""Unit tests for splits table functionality."""

import pytest
from sqlalchemy import text


def test_splits_table_structure(db_session):
    """Test that splits table has correct structure."""
    # Check table exists
    result = db_session.execute(text("""
        SELECT column_name, data_type, is_nullable, column_default, character_maximum_length, numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_name = 'splits'
        ORDER BY ordinal_position
    """))
    columns = result.fetchall()

    # Convert to dict for easier checking
    column_dict = {row[0]: {"type": row[1], "nullable": row[2], "default": row[3], "character_maximum_length": row[4] if len(row) > 4 else None, "precision": str(row[5]) if row[5] is not None else None, "scale": str(row[6]) if row[6] is not None else None} for row in columns}

    # Check required columns exist
    assert "id" in column_dict
    assert column_dict["id"]["type"] == "uuid"
    assert column_dict["id"]["nullable"] == "NO"

    assert "listing_id" in column_dict
    assert column_dict["listing_id"]["type"] == "uuid"
    assert column_dict["listing_id"]["nullable"] == "NO"

    assert "provider_id" in column_dict
    assert column_dict["provider_id"]["type"] == "uuid"
    assert column_dict["provider_id"]["nullable"] == "NO"

    assert "execution_date" in column_dict
    assert column_dict["execution_date"]["type"] == "date"
    assert column_dict["execution_date"]["nullable"] == "NO"

    assert "numerator" in column_dict
    assert column_dict["numerator"]["type"] == "integer"
    assert column_dict["numerator"]["nullable"] == "NO"

    assert "denominator" in column_dict
    assert column_dict["denominator"]["type"] == "integer"
    assert column_dict["denominator"]["nullable"] == "NO"

    assert "source_id" in column_dict
    assert column_dict["source_id"]["type"] == "character varying"
    assert column_dict["source_id"]["nullable"] == "YES"
    assert column_dict["source_id"]["character_maximum_length"] == 255  # VARCHAR(255)

    assert "created_at" in column_dict
    assert column_dict["created_at"]["type"] == "timestamp with time zone"
    assert column_dict["created_at"]["nullable"] == "NO"
    assert "now()" in column_dict["created_at"]["default"]

    assert "updated_at" in column_dict
    assert column_dict["updated_at"]["type"] == "timestamp with time zone"
    assert column_dict["updated_at"]["nullable"] == "NO"
    assert "now()" in column_dict["updated_at"]["default"]


def test_splits_table_constraints(db_session):
    """Test that splits table has correct constraints."""
    # Check primary key
    result = db_session.execute(text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'splits' AND constraint_type = 'PRIMARY KEY'
    """))
    pk_constraint = result.fetchone()
    assert pk_constraint is not None
    assert pk_constraint[0] == "splits_pkey"

    # Check foreign keys
    result = db_session.execute(text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'splits' AND constraint_type = 'FOREIGN KEY'
    """))
    fk_constraints = result.fetchall()
    assert len(fk_constraints) >= 2  # listing_id and provider_id FKs

    # Check unique constraint
    result = db_session.execute(text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'splits' AND constraint_type = 'UNIQUE'
    """))
    unique_constraints = result.fetchall()
    assert len(unique_constraints) >= 1
    constraint_names = [c[0] for c in unique_constraints]
    # Should have unique on listing_id, execution_date, provider_id, source_id
    assert any("listing_id" in c and "execution_date" in c and "provider_id" in c and "source_id" in c for c in constraint_names)

    # Check check constraints
    # Check using pg_constraint for better compatibility
    result = db_session.execute(text("""
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'splits'::regclass
          AND contype = 'c'
          AND conname IN ('chk_splits_positive')
    """))
    check_constraints = result.fetchall()
    assert len(check_constraints) == 1  # We expect exactly one check constraint: positive


def test_insert_split(db_session):
    """Test inserting a split record."""
    # First insert a provider
    provider_insert = """
        INSERT INTO data_providers (name, type)
        VALUES (:name, :type)
        RETURNING id
    """
    provider_result = db_session.execute(text(provider_insert), {
        "name": "Test Provider",
        "type": "price"
    })
    provider_id = provider_result.fetchone()[0]

    # First insert a company, exchange, and listing
    company_insert = """
        INSERT INTO companies (legal_name)
        VALUES (:legal_name)
        RETURNING id
    """
    company_result = db_session.execute(text(company_insert), {
        "legal_name": "Test Company"
    })
    company_id = company_result.fetchone()[0]

    exchange_insert = """
        INSERT INTO exchanges (code, name)
        VALUES (:code, :name)
        RETURNING id
    """
    exchange_result = db_session.execute(text(exchange_insert), {
        "code": "TEST",
        "name": "Test Exchange"
    })
    exchange_id = exchange_result.fetchone()[0]

    listing_insert = """
        INSERT INTO company_listings (company_id, exchange_id, ticker)
        VALUES (:company_id, :exchange_id, :ticker)
        RETURNING id
    """
    listing_result = db_session.execute(text(listing_insert), {
        "company_id": company_id,
        "exchange_id": exchange_id,
        "ticker": "TST"
    })
    listing_id = listing_result.fetchone()[0]

    # Insert split (2-for-1 split)
    split_insert = """
        INSERT INTO splits (listing_id, provider_id, execution_date, numerator, denominator, source_id)
        VALUES (:listing_id, :provider_id, :execution_date, :numerator, :denominator, :source_id)
        RETURNING id
    """

    result = db_session.execute(text(split_insert), {
        "listing_id": listing_id,
        "provider_id": provider_id,
        "execution_date": "2023-06-15",
        "numerator": 2,
        "denominator": 1,
        "source_id": "SPLIT2023"
    })

    split_id = result.fetchone()[0]
    db_session.commit()

    # Verify the split was inserted correctly
    select_sql = """
        SELECT listing_id, provider_id, execution_date, numerator, denominator, source_id
        FROM splits WHERE id = :split_id
    """

    result = db_session.execute(text(select_sql), {
        "split_id": split_id
    })
    split = result.fetchone()

    assert split is not None
    assert split[0] == listing_id
    assert split[1] == provider_id
    assert str(split[2]) == "2023-06-15"  # execution_date
    assert split[3] == 2  # numerator
    assert split[4] == 1  # denominator
    assert split[5] == "SPLIT2023"  # source_id