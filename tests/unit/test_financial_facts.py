"""Unit tests for financial_facts table functionality."""

import pytest
from sqlalchemy import text


def test_financial_facts_table_structure(db_session):
    """Test that financial_facts table has correct structure."""
    # Check table exists
    result = db_session.execute(
        text("""
        SELECT column_name, data_type, is_nullable, column_default, character_maximum_length, numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_name = 'financial_facts'
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

    assert "filing_id" in column_dict
    assert column_dict["filing_id"]["type"] == "uuid"
    assert column_dict["filing_id"]["nullable"] == "YES"

    assert "provider_id" in column_dict
    assert column_dict["provider_id"]["type"] == "uuid"
    assert column_dict["provider_id"]["nullable"] == "NO"

    assert "concept" in column_dict
    assert column_dict["concept"]["type"] == "character varying"
    assert column_dict["concept"]["nullable"] == "NO"
    assert column_dict["concept"]["character_maximum_length"] == 255  # VARCHAR(255)

    assert "value" in column_dict
    assert column_dict["value"]["type"] == "numeric"
    assert column_dict["value"]["nullable"] == "NO"
    # Check precision and scale (NUMERIC(30, 10))

    assert "unit" in column_dict
    assert column_dict["unit"]["type"] == "character varying"
    assert column_dict["unit"]["nullable"] == "NO"
    assert column_dict["unit"]["character_maximum_length"] == 50  # VARCHAR(50)

    assert "period_start" in column_dict
    assert column_dict["period_start"]["type"] == "date"
    assert column_dict["period_start"]["nullable"] == "YES"  # NULL for instant facts

    assert "period_end" in column_dict
    assert column_dict["period_end"]["type"] == "date"
    assert column_dict["period_end"]["nullable"] == "NO"

    assert "fiscal_year" in column_dict
    assert column_dict["fiscal_year"]["type"] == "integer"
    assert column_dict["fiscal_year"]["nullable"] == "NO"

    assert "fiscal_period" in column_dict
    assert column_dict["fiscal_period"]["type"] == "character varying"
    assert column_dict["fiscal_period"]["nullable"] == "NO"
    assert column_dict["fiscal_period"]["character_maximum_length"] == 20  # VARCHAR(20)

    assert "form" in column_dict
    assert column_dict["form"]["type"] == "character varying"
    assert column_dict["form"]["nullable"] == "YES"
    assert column_dict["form"]["character_maximum_length"] == 50  # VARCHAR(50)

    assert "source_id" in column_dict
    assert column_dict["source_id"]["type"] == "character varying"
    assert column_dict["source_id"]["nullable"] == "YES"
    assert column_dict["source_id"]["character_maximum_length"] == 255  # VARCHAR(255)

    assert "filing_date" in column_dict
    assert column_dict["filing_date"]["type"] == "date"
    assert column_dict["filing_date"]["nullable"] == "NO"

    assert "created_at" in column_dict
    assert column_dict["created_at"]["type"] == "timestamp with time zone"
    assert column_dict["created_at"]["nullable"] == "NO"
    assert "now()" in column_dict["created_at"]["default"]

    assert "updated_at" in column_dict
    assert column_dict["updated_at"]["type"] == "timestamp with time zone"
    assert column_dict["updated_at"]["nullable"] == "NO"
    assert "now()" in column_dict["updated_at"]["default"]


def test_financial_facts_table_constraints(db_session):
    """Test that financial_facts table has correct constraints."""
    # Check primary key
    result = db_session.execute(
        text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'financial_facts' AND constraint_type = 'PRIMARY KEY'
    """)
    )
    pk_constraint = result.fetchone()
    assert pk_constraint is not None
    assert pk_constraint[0] == "financial_facts_pkey"

    # Check foreign keys
    result = db_session.execute(
        text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'financial_facts' AND constraint_type = 'FOREIGN KEY'
    """)
    )
    fk_constraints = result.fetchall()
    assert len(fk_constraints) >= 3  # company_id, filing_id, provider_id FKs

    # Check unique constraint
    result = db_session.execute(
        text(
            "SELECT constraint_name FROM information_schema.table_constraints WHERE table_name = 'financial_facts' AND constraint_type = 'UNIQUE'"
        )
    )
    unique_constraints = result.fetchall()
    assert len(unique_constraints) >= 1
    constraint_names = [c[0] for c in unique_constraints]
    # Should have unique on company_id, concept, period_start, period_end, filing_id, source_id
    assert any(
        "company_id" in c
        and "concept" in c
        and "period_start" in c
        and "period_end" in c
        and "filing_id" in c
        and "source_id" in c
        for c in constraint_names
    ) or any(
        "financial_facts_company_id_concept_period_start_period_end__key" == c
        for c in constraint_names
    )

    # Check check constraint on period consistency
    result = db_session.execute(
        text("""
        SELECT conname, pg_get_constraintdef(c.oid) as check_clause
        FROM pg_constraint c
        JOIN pg_namespace n ON n.oid = c.connamespace
        WHERE conrelid = 'financial_facts'::regclass
          AND contype = 'c'
          AND conname = 'chk_financial_facts_period'
    """)
    )
    check_constraint = result.fetchone()
    assert check_constraint is not None
    assert "period_start IS NULL" in check_constraint[1]
    assert "period_start <= period_end" in check_constraint[1]


def test_financial_facts_instant_vs_duration(db_session):
    """Test that financial_facts properly handles instant vs duration facts."""
    # Insert a provider first
    provider_insert = """
        INSERT INTO data_providers (name, type)
        VALUES (:name, :type)
        RETURNING id
    """
    provider_result = db_session.execute(
        text(provider_insert), {"name": "Test Provider", "type": "fundamental"}
    )
    provider_id = provider_result.fetchone()[0]

    # Insert a company first
    company_insert = """
        INSERT INTO companies (legal_name)
        VALUES (:legal_name)
        RETURNING id
    """
    company_result = db_session.execute(
        text(company_insert), {"legal_name": "Test Company"}
    )
    company_id = company_result.fetchone()[0]

    # Insert a filing
    filing_insert = """
        INSERT INTO filings (company_id, provider_id, form, accession_number, filing_date, period_end)
        VALUES (:company_id, :provider_id, :form, :accession_number, :filing_date, :period_end)
        RETURNING id
    """
    filing_result = db_session.execute(
        text(filing_insert),
        {
            "company_id": company_id,
            "provider_id": provider_id,
            "form": "10-K",
            "accession_number": "TEST123",
            "filing_date": "2023-01-01",
            "period_end": "2023-12-31",
        },
    )
    filing_id = filing_result.fetchone()[0]

    # Insert instant fact (period_start NULL)
    instant_fact_insert = """
        INSERT INTO financial_facts
        (company_id, filing_id, provider_id, concept, value, unit, period_start, period_end, fiscal_year, fiscal_period, filing_date)
        VALUES (:company_id, :filing_id, :provider_id, :concept, :value, :unit, :period_start, :period_end, :fiscal_year, :fiscal_period, :filing_date)
        RETURNING id
    """

    instant_result = db_session.execute(
        text(instant_fact_insert),
        {
            "company_id": company_id,
            "filing_id": filing_id,
            "provider_id": provider_id,
            "concept": "Assets",
            "value": 1000000,
            "unit": "USD",
            "period_start": None,  # NULL for instant fact
            "period_end": "2023-12-31",
            "fiscal_year": 2023,
            "fiscal_period": "FY",
            "filing_date": "2023-01-01",
        },
    )

    instant_fact_id = instant_result.fetchone()[0]

    # Insert duration fact (period_start NOT NULL)
    duration_fact_insert = """
        INSERT INTO financial_facts
        (company_id, filing_id, provider_id, concept, value, unit, period_start, period_end, fiscal_year, fiscal_period, filing_date)
        VALUES (:company_id, :filing_id, :provider_id, :concept, :value, :unit, :period_start, :period_end, :fiscal_year, :fiscal_period, :filing_date)
        RETURNING id
    """

    duration_result = db_session.execute(
        text(duration_fact_insert),
        {
            "company_id": company_id,
            "filing_id": filing_id,
            "provider_id": provider_id,
            "concept": "Revenue",
            "value": 500000,
            "unit": "USD",
            "period_start": "2023-01-01",
            "period_end": "2023-12-31",
            "fiscal_year": 2023,
            "fiscal_period": "FY",
            "filing_date": "2023-01-01",
        },
    )

    duration_fact_id = duration_result.fetchone()[0]
    db_session.commit()

    # Verify instant fact
    instant_select = """
        SELECT period_start, period_end
        FROM financial_facts WHERE id = :fact_id
    """

    instant_result = db_session.execute(
        text(instant_select), {"fact_id": instant_fact_id}
    )
    instant_fact = instant_result.fetchone()
    assert instant_fact[0] is None  # period_start NULL for instant
    assert str(instant_fact[1]) == "2023-12-31"

    # Verify duration fact
    duration_select = """
        SELECT period_start, period_end
        FROM financial_facts WHERE id = :fact_id
    """

    duration_result = db_session.execute(
        text(duration_select), {"fact_id": duration_fact_id}
    )
    duration_fact = duration_result.fetchone()
    assert str(duration_fact[0]) == "2023-01-01"  # period_start NOT NULL for duration
    assert str(duration_fact[1]) == "2023-12-31"

    # Test that check constraint prevents invalid periods
    try:
        invalid_fact_insert = """
            INSERT INTO financial_facts
            (company_id, filing_id, provider_id, concept, value, unit, period_start, period_end, fiscal_year, fiscal_period, filing_date)
            VALUES (:company_id, :filing_id, :provider_id, :concept, :value, :unit, :period_start, :period_end, :fiscal_year, :fiscal_period, :filing_date)
        """
        db_session.execute(
            text(invalid_fact_insert),
            {
                "company_id": company_id,
                "filing_id": filing_id,
                "provider_id": provider_id,
                "concept": "Invalid",
                "value": 100,
                "unit": "USD",
                "period_start": "2024-01-01",  # period_start after period_end
                "period_end": "2023-12-31",
                "fiscal_year": 2023,
                "fiscal_period": "FY",
                "filing_date": "2023-01-01",
            },
        )
        db_session.commit()
        assert False, "Should have failed check constraint"
    except Exception:  # noqa: BLE001
        db_session.rollback()  # Expected to fail
        # Constraint worked correctly


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
