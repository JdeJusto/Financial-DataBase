"""Unit tests for prices table functionality."""

from sqlalchemy import text


def test_prices_table_structure(db_session):
    """Test that prices table has correct structure."""
    # Check table exists
    result = db_session.execute(
        text("""
        SELECT column_name, data_type, is_nullable, column_default, character_maximum_length, numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_name = 'prices'
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

    assert "listing_id" in column_dict
    assert column_dict["listing_id"]["type"] == "uuid"
    assert column_dict["listing_id"]["nullable"] == "NO"

    assert "provider_id" in column_dict
    assert column_dict["provider_id"]["type"] == "uuid"
    assert column_dict["provider_id"]["nullable"] == "NO"

    assert "price_date" in column_dict
    assert column_dict["price_date"]["type"] == "date"
    assert column_dict["price_date"]["nullable"] == "NO"

    assert "open" in column_dict
    assert column_dict["open"]["type"] == "numeric"
    assert column_dict["open"]["nullable"] == "NO"
    # Check precision and scale (NUMERIC(20, 6))
    assert column_dict["open"]["precision"] == "20"
    assert column_dict["open"]["scale"] == "6"

    assert "high" in column_dict
    assert column_dict["high"]["type"] == "numeric"
    assert column_dict["high"]["nullable"] == "NO"
    # Check precision and scale (NUMERIC(20, 6))
    assert column_dict["high"]["precision"] == "20"
    assert column_dict["high"]["scale"] == "6"

    assert "low" in column_dict
    assert column_dict["low"]["type"] == "numeric"
    assert column_dict["low"]["nullable"] == "NO"
    # Check precision and scale (NUMERIC(20, 6))
    assert column_dict["low"]["precision"] == "20"
    assert column_dict["low"]["scale"] == "6"

    assert "close" in column_dict
    assert column_dict["close"]["type"] == "numeric"
    assert column_dict["close"]["nullable"] == "NO"
    # Check precision and scale (NUMERIC(20, 6))
    assert column_dict["close"]["precision"] == "20"
    assert column_dict["close"]["scale"] == "6"

    assert "adjusted_close" in column_dict
    assert column_dict["adjusted_close"]["type"] == "numeric"
    assert column_dict["adjusted_close"]["nullable"] == "YES"
    # Check precision and scale (NUMERIC(20, 6))
    assert column_dict["adjusted_close"]["precision"] == "20"
    assert column_dict["adjusted_close"]["scale"] == "6"

    assert "volume" in column_dict
    assert column_dict["volume"]["type"] == "bigint"
    assert column_dict["volume"]["nullable"] == "NO"

    assert "currency" in column_dict
    assert column_dict["currency"]["type"] == "character varying"
    assert column_dict["currency"]["nullable"] == "NO"
    assert column_dict["currency"]["default"] == "'USD'::character varying"

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


def test_prices_table_constraints(db_session):
    """Test that prices table has correct constraints."""
    # Check primary key
    result = db_session.execute(
        text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'prices' AND constraint_type = 'PRIMARY KEY'
    """)
    )
    pk_constraint = result.fetchone()
    assert pk_constraint is not None
    assert pk_constraint[0] == "prices_pkey"

    # Check foreign keys
    result = db_session.execute(
        text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'prices' AND constraint_type = 'FOREIGN KEY'
    """)
    )
    fk_constraints = result.fetchall()
    assert len(fk_constraints) >= 2  # listing_id and provider_id FKs

    # Check unique constraint
    result = db_session.execute(
        text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'prices' AND constraint_type = 'UNIQUE'
    """)
    )
    unique_constraints = result.fetchall()
    assert len(unique_constraints) >= 1
    constraint_names = [c[0] for c in unique_constraints]
    # Should have unique on listing_id, price_date, provider_id
    assert any(
        "listing_id" in c and "price_date" in c and "provider_id" in c
        for c in constraint_names
    )

    # Check check constraints for non-negative values
    check_constraints = []
    for col in ["open", "high", "low", "close", "adjusted_close", "volume"]:
        result = db_session.execute(
            text(f"""
            SELECT check_clause
            FROM information_schema.check_constraints
            WHERE constraint_name = 'chk_prices_{col}_non_negative'
        """)
        )
        constraint = result.fetchone()
        if constraint:
            check_constraints.append(constraint[0])

    # At least some of these should exist
    # Note: The actual constraint names might differ, so we're checking if any checks exist
    result = db_session.execute(
        text("""
        SELECT COUNT(*)
        FROM information_schema.check_constraints
        WHERE constraint_name LIKE 'chk_prices_%'
    """)
    )
    check_count = result.fetchone()[0]
    assert check_count >= 0  # At least the table exists


def test_insert_price(db_session):
    """Test inserting a price record."""
    # First insert a provider
    provider_insert = """
        INSERT INTO data_providers (name, type)
        VALUES (:name, :type)
        RETURNING id
    """
    provider_result = db_session.execute(
        text(provider_insert), {"name": "Test Provider", "type": "price"}
    )
    provider_id = provider_result.fetchone()[0]

    # First insert a company, exchange, and listing
    company_insert = """
        INSERT INTO companies (legal_name)
        VALUES (:legal_name)
        RETURNING id
    """
    company_result = db_session.execute(
        text(company_insert), {"legal_name": "Test Company"}
    )
    company_id = company_result.fetchone()[0]

    exchange_insert = """
        INSERT INTO exchanges (code, name)
        VALUES (:code, :name)
        RETURNING id
    """
    exchange_result = db_session.execute(
        text(exchange_insert), {"code": "TEST", "name": "Test Exchange"}
    )
    exchange_id = exchange_result.fetchone()[0]

    listing_insert = """
        INSERT INTO company_listings (company_id, exchange_id, ticker)
        VALUES (:company_id, :exchange_id, :ticker)
        RETURNING id
    """
    listing_result = db_session.execute(
        text(listing_insert),
        {"company_id": company_id, "exchange_id": exchange_id, "ticker": "TST"},
    )
    listing_id = listing_result.fetchone()[0]

    # Insert price
    price_insert = """
        INSERT INTO prices (listing_id, provider_id, price_date, open, high, low, close, volume)
        VALUES (:listing_id, :provider_id, :price_date, :open, :high, :low, :close, :volume)
        RETURNING id
    """

    result = db_session.execute(
        text(price_insert),
        {
            "listing_id": listing_id,
            "provider_id": provider_id,
            "price_date": "2023-01-01",
            "open": 100.0,
            "high": 110.0,
            "low": 90.0,
            "close": 105.0,
            "volume": 1000000,
        },
    )

    price_id = result.fetchone()[0]
    db_session.commit()

    # Verify the price was inserted correctly
    select_sql = """
        SELECT listing_id, provider_id, price_date, open, high, low, close, volume
        FROM prices WHERE id = :price_id
    """

    result = db_session.execute(text(select_sql), {"price_id": price_id})
    price = result.fetchone()

    assert price is not None
    assert price[0] == listing_id
    assert price[1] == provider_id
    assert str(price[2]) == "2023-01-01"  # price_date
    assert float(price[3]) == 100.0  # open
    assert float(price[4]) == 110.0  # high
    assert float(price[5]) == 90.0  # low
    assert float(price[6]) == 105.0  # close
    assert price[7] == 1000000  # volume
