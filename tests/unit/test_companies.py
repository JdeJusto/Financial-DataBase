"""Unit tests for companies table functionality."""

from sqlalchemy import text


def test_companies_table_structure(db_session):
    """Test that companies table has correct structure."""
    # Check table exists
    result = db_session.execute(
        text("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'companies'
        ORDER BY ordinal_position
    """)
    )
    columns = result.fetchall()

    # Convert to dict for easier checking
    column_dict = {
        row[0]: {"type": row[1], "nullable": row[2], "default": row[3]}
        for row in columns
    }

    # Check required columns exist
    assert "id" in column_dict
    assert column_dict["id"]["type"] == "uuid"
    assert column_dict["id"]["nullable"] == "NO"

    assert "legal_name" in column_dict
    assert column_dict["legal_name"]["type"] == "character varying"
    assert column_dict["legal_name"]["nullable"] == "NO"

    assert "country" in column_dict
    assert column_dict["country"]["type"] == "character varying"
    assert column_dict["country"]["nullable"] == "YES"

    assert "sector" in column_dict
    assert column_dict["sector"]["type"] == "character varying"
    assert column_dict["sector"]["nullable"] == "YES"

    assert "industry" in column_dict
    assert column_dict["industry"]["type"] == "character varying"
    assert column_dict["industry"]["nullable"] == "YES"

    assert "currency" in column_dict
    assert column_dict["currency"]["type"] == "character varying"
    assert column_dict["currency"]["nullable"] == "YES"
    assert column_dict["currency"]["default"] == "'USD'::character varying"

    assert "website" in column_dict
    assert column_dict["website"]["type"] == "character varying"
    assert column_dict["website"]["nullable"] == "YES"

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


def test_companies_table_constraints(db_session):
    """Test that companies table has correct constraints."""
    # Check primary key
    result = db_session.execute(
        text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'companies' AND constraint_type = 'PRIMARY KEY'
    """)
    )
    pk_constraint = result.fetchone()
    assert pk_constraint is not None
    assert pk_constraint[0] == "companies_pkey"

    # Check that there's no ticker column (as per audit requirement)
    result = db_session.execute(
        text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'companies' AND column_name = 'ticker'
    """)
    )
    ticker_column = result.fetchone()
    assert ticker_column is None, "companies table should not have a ticker column"


def test_insert_company(db_session):
    """Test inserting a company record."""
    insert_sql = """
        INSERT INTO companies (legal_name, country, sector, industry, currency, website, is_active)
        VALUES (:legal_name, :country, :sector, :industry, :currency, :website, :is_active)
        RETURNING id
    """

    result = db_session.execute(
        text(insert_sql),
        {
            "legal_name": "Test Company Inc.",
            "country": "USA",
            "sector": "Technology",
            "industry": "Software",
            "currency": "USD",
            "website": "https://testcompany.com",
            "is_active": True,
        },
    )

    company_id = result.fetchone()[0]
    db_session.commit()

    # Verify the company was inserted correctly
    select_sql = """
        SELECT legal_name, country, sector, industry, currency, website, is_active
        FROM companies WHERE id = :company_id
    """

    result = db_session.execute(text(select_sql), {"company_id": company_id})
    company = result.fetchone()

    assert company is not None
    assert company[0] == "Test Company Inc."
    assert company[1] == "USA"
    assert company[2] == "Technology"
    assert company[3] == "Software"
    assert company[4] == "USD"
    assert company[5] == "https://testcompany.com"
    assert company[6] is True
