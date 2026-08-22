"""Unit tests for splits table functionality."""

import pytest
from sqlalchemy import text


def test_splits_table_structure(db_session):
    """Test that splits table has correct structure."""
    # Check table exists
    result = db_session.execute(text("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'splits'
        ORDER BY ordinal_position
    """))
    columns = result.fetchall()
    
    # Convert to dict for easier checking
    column_dict = {row[0]: {"type": row[1], "nullable": row[2], "default": row[3]} for row in columns}
    
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
    assert column_dict["source_id"]["length"] == 255  # VARCHAR(255)
    
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
    assert any("listing_id" in c and "execution_date" in c and "provider_id" in c and "source_id" in c 
               for c in constraint_names)
    
    # Check check constraint for positive numerator and denominator
    result = db_session.execute(text("""
        SELECT check_clause
        FROM information_schema.check_constraints
        WHERE constraint_name = 'chk_splits_positive'
    """))
    check_constraint = result.fetchone()
    assert check_constraint is not None
    assert "numerator > 0 AND denominator > 0" in check_constraint[0]


def test_insert_split(db_session):
    """Test inserting a split record."""
    # First insert a company, exchange, and listing
    company_insert = """
        INSERT INTO companies (legal_name)
        VALUES (%s)
        RETURNING id
    """
    company_result = db_session.execute(text(company_insert), ("Test Company",))
    company_id = company_result.fetchone()[0]
    
    exchange_insert = """
        INSERT INTO exchanges (code, name)
        VALUES (%s, %s)
        RETURNING id
    """
    exchange_result = db_session.execute(text(exchange_insert), ("TEST", "Test Exchange"))
    exchange_id = exchange_result.fetchone()[0]
    
    listing_insert = """
        INSERT INTO company_listings (company_id, exchange_id, ticker)
        VALUES (%s, %s, %s)
        RETURNING id
    """
    listing_result = db_session.execute(text(listing_insert), (company_id, exchange_id, "TST"))
    listing_id = listing_result.fetchone()[0]
    
    # Insert split (2-for-1 split)
    split_insert = """
        INSERT INTO splits (listing_id, provider_id, execution_date, numerator, denominator)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """
    
    result = db_session.execute(text(split_insert), (
        listing_id,
        None,  # No provider for simplicity
        "2023-01-15",
        2,  # numerator
        1   # denominator
    ))
    
    split_id = result.fetchone()[0]
    db_session.commit()
    
    # Verify the split was inserted correctly
    select_sql = """
        SELECT listing_id, provider_id, execution_date, numerator, denominator
        FROM splits WHERE id = %s
    """
    
    result = db_session.execute(text(select_sql), (split_id,))
    split = result.fetchone()
    
    assert split is not None
    assert split[0] == listing_id
    assert split[1] is None
    assert str(split[2]) == "2023-01-15"  # execution_date
    assert split[3] == 2                  # numerator
    assert split[4] == 1                  # denominator
    
    # Test that check constraint prevents non-positive values
    try:
        invalid_split_insert = """
            INSERT INTO splits (listing_id, provider_id, execution_date, numerator, denominator)
            VALUES (%s, %s, %s, %s, %s)
        """
        db_session.execute(text(invalid_split_insert), (
            listing_id,
            None,  # No provider
            "2023-01-15",
            0,     # Invalid numerator (not > 0)
            1      # Valid denominator
        ))
        db_session.commit()
        assert False, "Should have failed check constraint for non-positive numerator"
    except Exception:
        db_session.rollback()  # Expected to fail
        pass  # Constraint worked correctly
    
    try:
        invalid_split_insert2 = """
            INSERT INTO splits (listing_id, provider_id, execution_date, numerator, denominator)
            VALUES (%s, %s, %s, %s, %s)
        """
        db_session.execute(text(invalid_split_insert2), (
            listing_id,
            None,  # No provider
            "2023-01-15",
            2,     # Valid numerator
            0      # Invalid denominator (not > 0)
        ))
        db_session.commit()
        assert False, "Should have failed check constraint for non-positive denominator"
    except Exception:
        db_session.rollback()  # Expected to fail
        pass  # Constraint worked correctly
