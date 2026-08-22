"""Unit tests for raw_documents table functionality."""

import pytest
from sqlalchemy import text


def test_raw_documents_table_structure(db_session):
    """Test that raw_documents table has correct structure."""
    # Check table exists
    result = db_session.execute(text("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'raw_documents'
        ORDER BY ordinal_position
    """))
    columns = result.fetchall()
    
    # Convert to dict for easier checking
    column_dict = {row[0]: {"type": row[1], "nullable": row[2], "default": row[3]} for row in columns}
    
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
    assert column_dict["source_identifier"]["length"] == 255  # VARCHAR(255)
    
    assert "storage_path" in column_dict
    assert column_dict["storage_path"]["type"] == "character varying"
    assert column_dict["storage_path"]["nullable"] == "NO"
    assert column_dict["storage_path"]["length"] == 500  # VARCHAR(500)
    
    assert "checksum" in column_dict
    assert column_dict["checksum"]["type"] == "character varying"
    assert column_dict["checksum"]["nullable"] == "YES"
    assert column_dict["checksum"]["length"] == 64  # VARCHAR(64) for SHA256 hex
    
    assert "content_type" in column_dict
    assert column_dict["content_type"]["type"] == "character varying"
    assert column_dict["content_type"]["nullable"] == "YES"
    assert column_dict["content_type"]["length"] == 100  # VARCHAR(100)
    
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
    result = db_session.execute(text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'raw_documents' AND constraint_type = 'PRIMARY KEY'
    """))
    pk_constraint = result.fetchone()
    assert pk_constraint is not None
    assert pk_constraint[0] == "raw_documents_pkey"
    
    # Check foreign keys
    result = db_session.execute(text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'raw_documents' AND constraint_type = 'FOREIGN KEY'
    """))
    fk_constraints = result.fetchall()
    assert len(fk_constraints) >= 1  # provider_id FK
    
    # Check unique constraint
    result = db_session.execute(text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'raw_documents' AND constraint_type = 'UNIQUE'
    """))
    unique_constraints = result.fetchall()
    assert len(unique_constraints) >= 1
    constraint_names = [c[0] for c in unique_constraints]
    # Should have unique on provider_id, source_identifier
    assert any("provider_id" in c and "source_identifier" in c for c in constraint_names)


def test_insert_raw_document(db_session):
    """Test inserting a raw document record."""
    # First insert a provider
    provider_insert = """
        INSERT INTO data_providers (name, display_name, type)
        VALUES (%s, %s, %s)
        RETURNING id
    """
    provider_result = db_session.execute(text(provider_insert), (
        "SEC",
        "Securities and Exchange Commission",
        "sec"
    ))
    provider_id = provider_result.fetchone()[0]
    
    # Insert raw document
    raw_doc_insert = """
        INSERT INTO raw_documents (provider_id, source_identifier, storage_path, checksum, content_type, is_processed)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    
    result = db_session.execute(text(raw_doc_insert), (
        provider_id,
        "0000320193-23-000106",  # Example SEC accession number
        "/data/sec/2023/0000320193-23-000106.txt",
        "a1b2c3d4e5f6...",  # Example SHA256 checksum (truncated)
        "text/plain",
        False
    ))
    
    raw_doc_id = result.fetchone()[0]
    db_session.commit()
    
    # Verify the raw document was inserted correctly
    select_sql = """
        SELECT provider_id, source_identifier, storage_path, checksum, content_type, is_processed
        FROM raw_documents WHERE id = %s
    """
    
    result = db_session.execute(text(select_sql), (raw_doc_id,))
    raw_doc = result.fetchone()
    
    assert raw_doc is not None
    assert raw_doc[0] == provider_id
    assert raw_doc[1] == "0000320193-23-000106"
    assert raw_doc[2] == "/data/sec/2023/0000320193-23-000106.txt"
    assert raw_doc[3] == "a1b2c3d4e5f6..."  # checksum
    assert raw_doc[4] == "text/plain"         # content_type
    assert raw_doc[5] is False                # is_processed
