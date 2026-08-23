"""Unit tests for company_identifiers table functionality."""

from sqlalchemy import text


def test_company_identifiers_table_structure(db_session):
    """Test that company_identifiers table has correct structure."""
    # Check table exists
    result = db_session.execute(text("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'company_identifiers'
        ORDER BY ordinal_position
    """))
    columns = result.fetchall()
    
    # Convert to dict for easier checking
    column_dict = {row[0]: {"type": row[1], "nullable": row[2], "default": row[3]} for row in columns}
    
    # Check required columns exist
    assert "id" in column_dict
    assert column_dict["id"]["type"] == "uuid"
    assert column_dict["id"]["nullable"] == "NO"
    
    assert "company_id" in column_dict
    assert column_dict["company_id"]["type"] == "uuid"
    assert column_dict["company_id"]["nullable"] == "NO"
    
    assert "identifier_type" in column_dict
    assert column_dict["identifier_type"]["type"] == "character varying"
    assert column_dict["identifier_type"]["nullable"] == "NO"
    
    assert "identifier_value" in column_dict
    assert column_dict["identifier_value"]["type"] == "character varying"
    assert column_dict["identifier_value"]["nullable"] == "NO"
    
    assert "provider_id" in column_dict
    assert column_dict["provider_id"]["type"] == "uuid"
    assert column_dict["provider_id"]["nullable"] == "YES"
    
    assert "is_primary" in column_dict
    assert column_dict["is_primary"]["type"] == "boolean"
    assert column_dict["is_primary"]["nullable"] == "YES"
    assert column_dict["is_primary"]["default"] == "false"
    
    assert "valid_from" in column_dict
    assert column_dict["valid_from"]["type"] == "date"
    assert column_dict["valid_from"]["nullable"] == "YES"
    
    assert "valid_to" in column_dict
    assert column_dict["valid_to"]["type"] == "date"
    assert column_dict["valid_to"]["nullable"] == "YES"
    
    assert "created_at" in column_dict
    assert column_dict["created_at"]["type"] == "timestamp with time zone"
    assert column_dict["created_at"]["nullable"] == "NO"
    assert "now()" in column_dict["created_at"]["default"]
    
    assert "updated_at" in column_dict
    assert column_dict["updated_at"]["type"] == "timestamp with time zone"
    assert column_dict["updated_at"]["nullable"] == "NO"
    assert "now()" in column_dict["updated_at"]["default"]


def test_company_identifiers_table_constraints(db_session):
    """Test that company_identifiers table has correct constraints."""
    # Check primary key
    result = db_session.execute(text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'company_identifiers' AND constraint_type = 'PRIMARY KEY'
    """))
    pk_constraint = result.fetchone()
    assert pk_constraint is not None
    assert pk_constraint[0] == "company_identifiers_pkey"
    
    # Check foreign key
    result = db_session.execute(text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'company_identifiers' AND constraint_type = 'FOREIGN KEY'
    """))
    fk_constraints = result.fetchall()
    assert len(fk_constraints) >= 1  # At least company_id FK
    
    # Check unique constraint per audit
    result = db_session.execute(text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'company_identifiers' AND constraint_type = 'UNIQUE'
    """))
    unique_constraints = result.fetchall()
    constraint_names = [c[0] for c in unique_constraints]
    
    # Should have the correct unique constraint: company_id, identifier_type, provider_id, identifier_value
    # Note: PostgreSQL may truncate constraint names, so we check for the pattern
    expected_constraint_found = (
        "company_identifiers_company_id_identifier_type_provider_id_identifier_value_key" in constraint_names or
        any("company_id" in c and "identifier_type" in c and "provider_id" in c and "identifier_value" in c
            for c in constraint_names) or
        # Handle PostgreSQL truncation with double underscore
        any("company_identifiers_company_id_identifier_type_provider_id__" in c for c in constraint_names)
    )
    assert expected_constraint_found, f"Expected unique constraint not found in: {constraint_names}"
    
    # Verify there's NO unique constraint on just identifier_value (ticker) as per audit
    result = db_session.execute(text("""
        SELECT indexdef
        FROM pg_indexes
        WHERE tablename = 'company_identifiers' AND indexdef LIKE '%identifier_value%' AND indexdef LIKE '%unique%'
    """))
    unique_indexes = result.fetchall()
    
    # Check that there's no unique index on identifier_value alone where identifier_type = 'ticker'
    has_problematic_index = False
    for index in unique_indexes:
        index_def = index[0]
        if "identifier_value" in index_def and "WHERE" in index_def and "identifier_type" in index_def and "'ticker'" in index_def:
            has_problematic_index = True
            break
    
    assert not has_problematic_index, "Should not have unique index on identifier_value where identifier_type = 'ticker'"


def test_insert_company_identifier(db_session):
    """Test inserting a company identifier record."""
    # First insert a company
    company_insert = """
        INSERT INTO companies (legal_name)
        VALUES (:legal_name)
        RETURNING id
    """
    company_result = db_session.execute(text(company_insert), {
        "legal_name": "Test Company"
    })
    company_id = company_result.fetchone()[0]

    # Insert identifier
    identifier_insert = """
        INSERT INTO company_identifiers (company_id, identifier_type, identifier_value, provider_id, is_primary)
        VALUES (:company_id, :identifier_type, :identifier_value, :provider_id, :is_primary)
        RETURNING id
    """

    result = db_session.execute(text(identifier_insert), {
        "company_id": company_id,
        "identifier_type": "ticker",
        "identifier_value": "TEST",
        "provider_id": None,
        "is_primary": True
    })

    identifier_id = result.fetchone()[0]
    db_session.commit()

    # Verify the identifier was inserted correctly
    select_sql = """
        SELECT company_id, identifier_type, identifier_value, provider_id, is_primary
        FROM company_identifiers WHERE id = :identifier_id
    """

    result = db_session.execute(text(select_sql), {"identifier_id": identifier_id})
    identifier = result.fetchone()

    assert identifier is not None
    assert identifier[0] == company_id
    assert identifier[1] == "ticker"
    assert identifier[2] == "TEST"
    assert identifier[3] is None
    assert identifier[4] is True
