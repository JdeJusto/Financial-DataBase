"""Unit tests for import_runs table functionality."""

from sqlalchemy import text


def test_import_runs_table_structure(db_session):
    """Test that import_runs table has correct structure."""
    # Check table exists
    result = db_session.execute(text("""
        SELECT column_name, data_type, is_nullable, column_default, character_maximum_length, numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_name = 'import_runs'
        ORDER BY ordinal_position
    """))
    columns = result.fetchall()

    # Convert to dict for easier checking
    column_dict = {row[0]: {"type": row[1], "nullable": row[2], "default": row[3], "character_maximum_length": row[4] if len(row) > 4 else None, "precision": str(row[5]) if row[5] is not None else None, "scale": str(row[6]) if row[6] is not None else None} for row in columns}

    # Check required columns exist
    assert "id" in column_dict
    assert column_dict["id"]["type"] == "uuid"
    assert column_dict["id"]["nullable"] == "NO"

    assert "provider_id" in column_dict
    assert column_dict["provider_id"]["type"] == "uuid"
    assert column_dict["provider_id"]["nullable"] == "NO"

    assert "pipeline" in column_dict
    assert column_dict["pipeline"]["type"] == "character varying"
    assert column_dict["pipeline"]["nullable"] == "NO"
    assert column_dict["pipeline"]["character_maximum_length"] == 100  # VARCHAR(100)

    assert "status" in column_dict
    assert column_dict["status"]["type"] == "character varying"
    assert column_dict["status"]["nullable"] == "NO"
    assert column_dict["status"]["default"] == "'running'::character varying"

    assert "records_processed" in column_dict
    assert column_dict["records_processed"]["type"] == "integer"
    assert column_dict["records_processed"]["nullable"] == "YES"  # Nullable, default 0
    assert column_dict["records_processed"]["default"] == "0"

    assert "records_inserted" in column_dict
    assert column_dict["records_inserted"]["type"] == "integer"
    assert column_dict["records_inserted"]["nullable"] == "YES"  # Nullable, default 0
    assert column_dict["records_inserted"]["default"] == "0"

    assert "records_updated" in column_dict
    assert column_dict["records_updated"]["type"] == "integer"
    assert column_dict["records_updated"]["nullable"] == "YES"  # Nullable, default 0
    assert column_dict["records_updated"]["default"] == "0"

    assert "records_skipped" in column_dict
    assert column_dict["records_skipped"]["type"] == "integer"
    assert column_dict["records_skipped"]["nullable"] == "YES"  # Nullable, default 0
    assert column_dict["records_skipped"]["default"] == "0"

    assert "errors" in column_dict
    assert column_dict["errors"]["type"] == "jsonb"
    assert column_dict["errors"]["nullable"] == "YES"  # Nullable, default '{}'
    assert column_dict["errors"]["default"] == "'{}'::jsonb"

    assert "started_at" in column_dict
    assert column_dict["started_at"]["type"] == "timestamp with time zone"
    assert column_dict["started_at"]["nullable"] == "NO"
    assert "now()" in column_dict["started_at"]["default"]

    assert "finished_at" in column_dict
    assert column_dict["finished_at"]["type"] == "timestamp with time zone"
    assert column_dict["finished_at"]["nullable"] == "YES"

    assert "duration_seconds" in column_dict
    assert column_dict["duration_seconds"]["type"] == "integer"
    assert column_dict["duration_seconds"]["nullable"] == "YES"

    assert "created_at" in column_dict
    assert column_dict["created_at"]["type"] == "timestamp with time zone"
    assert column_dict["created_at"]["nullable"] == "NO"
    assert "now()" in column_dict["created_at"]["default"]


def test_import_runs_table_constraints(db_session):
    """Test that import_runs table has correct constraints."""
    # Check primary key
    result = db_session.execute(text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'import_runs' AND constraint_type = 'PRIMARY KEY'
    """))
    pk_constraint = result.fetchone()
    assert pk_constraint is not None
    assert pk_constraint[0] == "import_runs_pkey"

    # Check foreign keys
    result = db_session.execute(text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'import_runs' AND constraint_type = 'FOREIGN KEY'
    """))
    fk_constraints = result.fetchall()
    assert len(fk_constraints) >= 1  # provider_id FK

    # Check check constraints
    # Check using pg_constraint for better compatibility
    result = db_session.execute(text("""
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'import_runs'::regclass
          AND contype = 'c'
          AND conname IN ('chk_import_runs_status')
    """))
    check_constraints = result.fetchall()
    assert len(check_constraints) == 1  # We expect exactly one check constraint: status


def test_insert_import_run(db_session):
    """Test inserting an import run record."""
    # First insert a provider
    provider_insert = """
        INSERT INTO data_providers (name, type)
        VALUES (:name, :type)
        RETURNING id
    """
    provider_result = db_session.execute(text(provider_insert), {
        "name": "Test Provider",
        "type": "sec"
    })
    provider_id = provider_result.fetchone()[0]

    # Insert import run
    import_run_insert = """
        INSERT INTO import_runs (provider_id, pipeline, status, records_processed, records_inserted, records_updated, records_skipped, errors)
        VALUES (:provider_id, :pipeline, :status, :records_processed, :records_inserted, :records_updated, :records_skipped, :errors)
        RETURNING id
    """

    result = db_session.execute(text(import_run_insert), {
        "provider_id": provider_id,
        "pipeline": "filings",
        "status": "running",
        "records_processed": 100,
        "records_inserted": 95,
        "records_updated": 3,
        "records_skipped": 2,
        "errors": '{"validation_errors": ["Missing required field", "Invalid format"]}'
    })

    import_run_id = result.fetchone()[0]
    db_session.commit()

    # Verify the import run was inserted correctly
    select_sql = """
        SELECT provider_id, pipeline, status, records_processed, records_inserted, records_updated, records_skipped, errors
        FROM import_runs WHERE id = :import_run_id
    """

    result = db_session.execute(text(select_sql), {
        "import_run_id": import_run_id
    })
    import_run = result.fetchone()

    assert import_run is not None
    assert import_run[0] == provider_id
    assert import_run[1] == "filings"
    assert import_run[2] == "running"
    assert import_run[3] == 100  # records_processed
    assert import_run[4] == 95   # records_inserted
    assert import_run[5] == 3    # records_updated
    assert import_run[6] == 2    # records_skipped
    # Note: errors column comparison might need adjustment based on how JSONB is returned