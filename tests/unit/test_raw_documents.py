"""Unit tests for raw_documents table functionality."""

from sqlalchemy import text


def test_raw_documents_table_structure(db_session):
    """Test that raw_documents table has correct structure."""
    # Check table exists
    result = db_session.execute(
        text("""
        SELECT column_name, data_type, is_nullable, column_default, character_maximum_length, numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_name = 'raw_documents'
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

    assert "provider_id" in column_dict
    assert column_dict["provider_id"]["type"] == "uuid"
    assert column_dict["provider_id"]["nullable"] == "NO"

    assert "source_identifier" in column_dict
    assert column_dict["source_identifier"]["type"] == "character varying"
    assert column_dict["source_identifier"]["nullable"] == "NO"
    assert (
        column_dict["source_identifier"]["character_maximum_length"] == 255
    )  # VARCHAR(255)

    assert "storage_path" in column_dict
    assert column_dict["storage_path"]["type"] == "character varying"
    assert column_dict["storage_path"]["nullable"] == "NO"
    assert (
        column_dict["storage_path"]["character_maximum_length"] == 500
    )  # VARCHAR(500)

    assert "checksum" in column_dict
    assert column_dict["checksum"]["type"] == "character varying"
    assert column_dict["checksum"]["nullable"] == "YES"
    assert column_dict["checksum"]["character_maximum_length"] == 64  # VARCHAR(64)

    assert "content_type" in column_dict
    assert column_dict["content_type"]["type"] == "character varying"
    assert column_dict["content_type"]["nullable"] == "YES"
    assert (
        column_dict["content_type"]["character_maximum_length"] == 100
    )  # VARCHAR(100)

    assert "retrieved_at" in column_dict
    assert column_dict["retrieved_at"]["type"] == "timestamp with time zone"
    assert column_dict["retrieved_at"]["nullable"] == "NO"
    assert "now()" in column_dict["retrieved_at"]["default"]

    assert "metadata" in column_dict
    assert column_dict["metadata"]["type"] == "jsonb"
    assert column_dict["metadata"]["nullable"] == "YES"
    assert column_dict["metadata"]["default"] == "'{}'::jsonb"

    assert "is_processed" in column_dict
    assert column_dict["is_processed"]["type"] == "boolean"
    assert column_dict["is_processed"]["nullable"] == "YES"
    assert column_dict["is_processed"]["default"] == "false"

    assert "created_at" in column_dict
    assert column_dict["created_at"]["type"] == "timestamp with time zone"
    assert column_dict["created_at"]["nullable"] == "NO"
    assert "now()" in column_dict["created_at"]["default"]

    assert "updated_at" in column_dict
    assert column_dict["updated_at"]["type"] == "timestamp with time zone"
    assert column_dict["updated_at"]["nullable"] == "NO"
    assert "now()" in column_dict["updated_at"]["default"]


def test_raw_documents_table_constraints(db_session):
    """Test that raw_documents table has correct constraints."""
    # Check primary key
    result = db_session.execute(
        text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'raw_documents' AND constraint_type = 'PRIMARY KEY'
    """)
    )
    pk_constraint = result.fetchone()
    assert pk_constraint is not None
    assert pk_constraint[0] == "raw_documents_pkey"

    # Check foreign keys
    result = db_session.execute(
        text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'raw_documents' AND constraint_type = 'FOREIGN KEY'
    """)
    )
    fk_constraints = result.fetchall()
    assert len(fk_constraints) >= 1  # provider_id FK

    # Check unique constraint
    result = db_session.execute(
        text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'raw_documents' AND constraint_type = 'UNIQUE'
    """)
    )
    unique_constraints = result.fetchall()
    assert len(unique_constraints) >= 1
    constraint_names = [c[0] for c in unique_constraints]
    # Should have unique on provider_id, source_identifier
    assert any(
        "provider_id" in c and "source_identifier" in c for c in constraint_names
    )


def test_insert_raw_document(db_session):
    """Test inserting a raw document record."""
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

    # Insert raw document
    raw_document_insert = """
        INSERT INTO raw_documents (provider_id, source_identifier, storage_path, checksum, content_type, is_processed)
        VALUES (:provider_id, :source_identifier, :storage_path, :checksum, :content_type, :is_processed)
        RETURNING id
    """

    result = db_session.execute(
        text(raw_document_insert),
        {
            "provider_id": provider_id,
            "source_identifier": "0000320193-23-000107",
            "storage_path": "/data/raw/0000320193-23-000107.txt",
            "checksum": "a" * 64,  # 64-character SHA256 hash
            "content_type": "text/plain",
            "is_processed": False,
        },
    )

    raw_document_id = result.fetchone()[0]
    db_session.commit()

    # Verify the raw document was inserted correctly
    select_sql = """
        SELECT provider_id, source_identifier, storage_path, checksum, content_type, is_processed
        FROM raw_documents WHERE id = :raw_document_id
    """

    result = db_session.execute(text(select_sql), {"raw_document_id": raw_document_id})
    raw_document = result.fetchone()

    assert raw_document is not None
    assert raw_document[0] == provider_id
    assert raw_document[1] == "0000320193-23-000107"
    assert raw_document[2] == "/data/raw/0000320193-23-000107.txt"
    assert raw_document[3] == "a" * 64
    assert raw_document[4] == "text/plain"
    assert raw_document[5] is False
