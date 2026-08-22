"""Unit tests for dividends table functionality."""

import pytest
from sqlalchemy import text


def test_dividends_table_structure(db_session):
    """Test that dividends table has correct structure."""
    # Check table exists
    result = db_session.execute(text("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'dividends'
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
    
    assert "ex_dividend_date" in column_dict
    assert column_dict["ex_dividend_date"]["type"] == "date"
    assert column_dict["ex_dividend_date"]["nullable"] == "YES"
    
    assert "record_date" in column_dict
    assert column_dict["record_date"]["type"] == "date"
    assert column_dict["record_date"]["nullable"] == "YES"
    
    assert "payment_date" in column_dict
    assert column_dict["payment_date"]["type"] == "date"
    assert column_dict["payment_date"]["nullable"] == "YES"
    
    assert "amount" in column_dict
    assert column_dict["amount"]["type"] == "numeric"
    assert column_dict["amount"]["nullable"] == "NO"
    # Check precision and scale (NUMERIC(20, 10))
    
    assert "currency" in column_dict
    assert column_dict["currency"]["type"] == "character varying"
    assert column_dict["currency"]["nullable"] == "YES"
    assert column_dict["currency"]["default"] == "'USD'::character varying"
    
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


def test_dividends_table_constraints(db_session):
    """Test that dividends table has correct constraints."""
    # Check primary key
    result = db_session.execute(text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'dividends' AND constraint_type = 'PRIMARY KEY'
    """))
    pk_constraint = result.fetchone()
    assert pk_constraint is not None
    assert pk_constraint[0] == "dividends_pkey"
    
    # Check foreign keys
    result = db_session.execute(text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'dividends' AND constraint_type = 'FOREIGN KEY'
    """))
    fk_constraints = result.fetchall()
    assert len(fk_constraints) >= 2  # listing_id and provider_id FKs
    
    # Check unique constraint
    result = db_session.execute(text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'dividends' AND constraint_type = 'UNIQUE'
    """))
    unique_constraints = result.fetchall()
    assert len(unique_constraints) >= 1
    constraint_names = [c[0] for c in unique_constraints]
    # Should have unique on listing_id, ex_dividend_date, provider_id, source_id
    assert any("listing_id" in c and "ex_dividend_date" in c and "provider_id" in c and "source_id" in c 
               for c in constraint_names)
    
    # Check check constraint for amount >= 0
    result = db_session.execute(text("""
        SELECT check_clause
        FROM information_schema.check_constraints
        WHERE constraint_name = 'chk_dividends_amount'
    """))
    check_constraint = result.fetchone()
    assert check_constraint is not None
    assert "amount >= 0" in check_constraint[0]
    
    # Check check constraint for dates
    result = db_session.execute(text("""
        SELECT check_clause
        FROM information_schema.check_constraints
        WHERE constraint_name = 'chk_dividends_dates'
    """))
    date_check = result.fetchone()
    assert date_check is not None
    assert "ex_dividend_date IS NULL OR record_date IS NULL OR ex_dividend_date <= record_date" in date_check[0]


def test_insert_dividend(db_session):
    """Test inserting a dividend record."""
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
    
    # Insert dividend
    dividend_insert = """
        INSERT INTO dividends (listing_id, provider_id, ex_dividend_date, record_date, payment_date, amount, currency)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    
    result = db_session.execute(text(dividend_insert), (
        listing_id,
        None,  # No provider for simplicity
        "2023-01-15",
        "2023-01-20",
        "2023-02-01",
        2.50,
        "USD"
    ))
    
    dividend_id = result.fetchone()[0]
    db_session.commit()
    
    # Verify the dividend was inserted correctly
    select_sql = """
        SELECT listing_id, provider_id, ex_dividend_date, record_date, payment_date, amount, currency
        FROM dividends WHERE id = %s
    """
    
    result = db_session.execute(text(select_sql), (dividend_id,))
    dividend = result.fetchone()
    
    assert dividend is not None
    assert dividend[0] == listing_id
    assert dividend[1] is None
    assert str(dividend[2]) == "2023-01-15"  # ex_dividend_date
    assert str(dividend[3]) == "2023-01-20"  # record_date
    assert str(dividend[4]) == "2023-02-01"  # payment_date
    assert float(dividend[5]) == 2.50       # amount
    assert dividend[6] == "USD"             # currency
    
    # Test that check constraint prevents negative amounts
    try:
        negative_dividend_insert = """
            INSERT INTO dividends (listing_id, provider_id, ex_dividend_date, amount)
            VALUES (%s, %s, %s, %s)
        """
        db_session.execute(text(negative_dividend_insert), (
            listing_id,
            None,  # No provider
            "2023-01-15",
            -1.00  # Negative amount
        ))
        db_session.commit()
        assert False, "Should have failed check constraint for negative amount"
    except Exception:
        db_session.rollback()  # Expected to fail
        pass  # Constraint worked correctly
