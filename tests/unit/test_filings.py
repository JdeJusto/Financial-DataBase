"""Unit tests for filings table functionality."""

from sqlalchemy import text


def test_filings_table_structure(db_session):
    """Test that filings table has correct structure."""
    # Check table exists
    result = db_session.execute(
        text("""
        SELECT column_name, data_type, is_nullable, column_default, character_maximum_length, numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_name = 'filings'
        ORDER BY ordinal_position
    """)
    )
    columns = result.fetchall()

    # Convert to dict for easier checking
    column_dict = {
        row[0]: {
            "type": row[1],
            "nullable": row[2],
            "default": row[3],
            "character_maximum_length": row[4] if len(row) > 4 else None,
            "precision": str(row[5]) if row[5] is not None else None,
            "scale": str(row[6]) if row[6] is not None else None,
        }
        for row in columns
    }

    # Check required columns exist
    assert "id" in column_dict
    assert column_dict["id"]["type"] == "uuid"
    assert column_dict["id"]["nullable"] == "NO"

    assert "company_id" in column_dict
    assert column_dict["company_id"]["type"] == "uuid"
    assert column_dict["company_id"]["nullable"] == "NO"

    assert "provider_id" in column_dict
    assert column_dict["provider_id"]["type"] == "uuid"
    assert column_dict["provider_id"]["nullable"] == "NO"

    assert "form" in column_dict
    assert column_dict["form"]["type"] == "character varying"
    assert column_dict["form"]["nullable"] == "NO"
    assert column_dict["form"]["character_maximum_length"] == 50  # VARCHAR(50)

    assert "accession_number" in column_dict
    assert column_dict["accession_number"]["type"] == "character varying"
    assert column_dict["accession_number"]["nullable"] == "NO"
    assert (
        column_dict["accession_number"]["character_maximum_length"] == 255
    )  # VARCHAR(255)

    assert "filing_date" in column_dict
    assert column_dict["filing_date"]["type"] == "date"
    assert column_dict["filing_date"]["nullable"] == "NO"

    assert "period_start" in column_dict
    assert column_dict["period_start"]["type"] == "date"
    assert (
        column_dict["period_start"]["nullable"] == "YES"
    )  # nullable for instant/point-in-time filings

    assert "period_end" in column_dict
    assert column_dict["period_end"]["type"] == "date"
    # Nullable since migration 0017: SEC may omit period_of_report
    assert column_dict["period_end"]["nullable"] == "YES"

    assert "fiscal_year" in column_dict
    assert column_dict["fiscal_year"]["type"] == "integer"
    assert column_dict["fiscal_year"]["nullable"] == "YES"

    assert "fiscal_period" in column_dict
    assert column_dict["fiscal_period"]["type"] == "character varying"
    assert column_dict["fiscal_period"]["nullable"] == "YES"
    assert column_dict["fiscal_period"]["character_maximum_length"] == 20  # VARCHAR(20)

    assert "filing_url" in column_dict
    assert column_dict["filing_url"]["type"] == "character varying"
    assert column_dict["filing_url"]["nullable"] == "YES"
    assert column_dict["filing_url"]["character_maximum_length"] == 500  # VARCHAR(500)

    assert "raw_document_id" in column_dict
    assert column_dict["raw_document_id"]["type"] == "uuid"
    assert column_dict["raw_document_id"]["nullable"] == "YES"

    assert "is_amended" in column_dict
    assert column_dict["is_amended"]["type"] == "boolean"
    assert column_dict["is_amended"]["nullable"] == "YES"
    assert column_dict["is_amended"]["default"] == "false"

    assert "amended_by_filing_id" in column_dict
    assert column_dict["amended_by_filing_id"]["type"] == "uuid"
    assert column_dict["amended_by_filing_id"]["nullable"] == "YES"

    assert "created_at" in column_dict
    assert column_dict["created_at"]["type"] == "timestamp with time zone"
    assert column_dict["created_at"]["nullable"] == "NO"
    assert "now()" in column_dict["created_at"]["default"]

    assert "updated_at" in column_dict
    assert column_dict["updated_at"]["type"] == "timestamp with time zone"
    assert column_dict["updated_at"]["nullable"] == "NO"
    assert "now()" in column_dict["updated_at"]["default"]


def test_filings_table_constraints(db_session):
    """Test that filings table has correct constraints."""
    # Check primary key
    result = db_session.execute(
        text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'filings' AND constraint_type = 'PRIMARY KEY'
    """)
    )
    pk_constraint = result.fetchone()
    assert pk_constraint is not None
    assert pk_constraint[0] == "filings_pkey"

    # Check foreign keys
    result = db_session.execute(
        text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'filings' AND constraint_type = 'FOREIGN KEY'
    """)
    )
    fk_constraints = result.fetchall()
    assert len(fk_constraints) >= 2  # company_id and provider_id FKs

    # Check unique constraint
    result = db_session.execute(
        text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'filings' AND constraint_type = 'UNIQUE'
    """)
    )
    unique_constraints = result.fetchall()
    assert len(unique_constraints) >= 1
    constraint_names = [c[0] for c in unique_constraints]
    # Should have unique on provider_id, accession_number
    assert any("provider_id" in c and "accession_number" in c for c in constraint_names)


def test_insert_filing(db_session):
    """Test inserting a filing record."""
    # First insert a provider
    provider_insert = """
        INSERT INTO data_providers (name, type)
        VALUES (:name, :type)
        RETURNING id
    """
    provider_result = db_session.execute(
        text(provider_insert), {"name": "Test Provider", "type": "sec"}
    )
    provider_id = provider_result.fetchone()[0]

    # First insert a company
    company_insert = """
        INSERT INTO companies (legal_name)
        VALUES (:legal_name)
        RETURNING id
    """
    company_result = db_session.execute(
        text(company_insert), {"legal_name": "Test Company"}
    )
    company_id = company_result.fetchone()[0]

    # Insert filing
    filing_insert = """
        INSERT INTO filings (company_id, provider_id, form, accession_number, filing_date, period_start, period_end, is_amended)
        VALUES (:company_id, :provider_id, :form, :accession_number, :filing_date, :period_start, :period_end, :is_amended)
        RETURNING id
    """

    result = db_session.execute(
        text(filing_insert),
        {
            "company_id": company_id,
            "provider_id": provider_id,
            "form": "10-K",
            "accession_number": "TEST123456",
            "filing_date": "2023-01-31",
            "period_start": "2023-01-01",
            "period_end": "2023-12-31",
            "is_amended": False,
        },
    )

    filing_id = result.fetchone()[0]
    db_session.commit()

    # Verify the filing was inserted correctly
    select_sql = """
        SELECT company_id, provider_id, form, accession_number, filing_date, period_start, period_end, is_amended
        FROM filings WHERE id = :filing_id
    """

    result = db_session.execute(text(select_sql), {"filing_id": filing_id})
    filing = result.fetchone()

    assert filing is not None
    assert filing[0] == company_id
    assert filing[1] == provider_id
    assert filing[2] == "10-K"
    assert filing[3] == "TEST123456"
    assert str(filing[4]) == "2023-01-31"  # filing_date
    assert str(filing[5]) == "2023-01-01"  # period_start
    assert str(filing[6]) == "2023-12-31"  # period_end
    assert filing[7] is False  # is_amended
