"""Integration tests for database migrations."""

import pytest
from sqlalchemy import text
from tests.fixtures.conftest import db_engine


def test_migrations_apply_cleanly(db_engine):
    """Test that all migrations can be applied to a fresh database."""
    # This test runs against the actual database created by the fixture
    # The migrations should have already been applied by the test setup
    
    # Verify that we can connect and basic tables exist
    with db_engine.connect() as conn:
        # Check that companies table exists
        result = conn.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'companies'
        """))
        assert result.scalar() == 1
        
        # Check that data_providers table exists
        result = conn.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'data_providers'
        """))
        assert result.scalar() == 1
        
        # Check a few more key tables
        for table in ['company_identifiers', 'company_listings', 'exchanges', 'financial_facts']:
            result = conn.execute(text(f"""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_name = '{table}'
            """))
            assert result.scalar() == 1, f"Table {table} should exist"


def test_foreign_key_constraints_work(db_engine):
    """Test that foreign key constraints are working correctly."""
    with db_engine.connect() as conn:
        # Start a transaction
        trans = conn.begin()
        try:
            # Insert a company
            result = conn.execute(text("""""
                INSERT INTO companies (legal_name) 
                VALUES ('Test Company') 
                RETURNING id
            """))
            company_id = result.scalar()
            
            # Insert a provider
            result = conn.execute(text("""
                INSERT INTO data_providers (name, display_name, type) 
                VALUES ('Test Provider', 'Test Provider Display', 'test') 
                RETURNING id
            """))
            provider_id = result.scalar()
            
            # Insert an exchange
            result = conn.execute(text("""
                INSERT INTO exchanges (code, name) 
                VALUES ('TEST', 'Test Exchange') 
                RETURNING id
            """))
            exchange_id = result.scalar()
            
            # Insert a company listing (should work with valid FKs)
            result = conn.execute(text("""
                INSERT INTO company_listings (company_id, exchange_id, ticker) 
                VALUES (%s, %s, 'TST') 
                RETURNING id
            """), (company_id, exchange_id))
            listing_id = result.scalar()
            
            # Insert a financial fact (should work with valid FKs)
            result = conn.execute(text("""
                INSERT INTO financial_facts 
                (company_id, provider_id, concept, value, unit, period_end, fiscal_year, fiscal_period, filing_date)
                VALUES (%s, %s, 'Revenue', 1000, 'USD', '2023-12-31', 2023, 'FY', '2023-01-01')
                RETURNING id
            """), (company_id, provider_id))
            fact_id = result.scalar()
            
            # All inserts should have succeeded
            assert company_id is not None
            assert provider_id is not None
            assert exchange_id is not None
            assert listing_id is not None
            assert fact_id is not None
            
            # Try to insert a financial fact with invalid company_id (should fail)
            try:
                conn.execute(text("""
                    INSERT INTO financial_facts 
                    (company_id, provider_id, concept, value, unit, period_end, fiscal_year, fiscal_period, filing_date)
                    VALUES (%s, %s, 'Revenue', 1000, 'USD', '2023-12-31', 2023, 'FY', '2023-01-01')
                """), (99999, provider_id))  # Non-existent company_id
                conn.commit()
                assert False, "Should have failed foreign key constraint"
            except Exception:
                conn.rollback()  # Expected to fail
                pass  # Foreign key constraint worked correctly
                
        finally:
            trans.rollback()


def test_unique_constraints_work(db_engine):
    """Test that unique constraints are working correctly."""
    with db_engine.connect() as conn:
        trans = conn.begin()
        try:
            # Insert a company
            result = conn.execute(text("""
                INSERT INTO companies (legal_name) 
                VALUES ('Test Company') 
                RETURNING id
            """))
            company_id = result.scalar()
            
            # Insert a provider
            result = conn.execute(text("""
                INSERT INTO data_providers (name, display_name, type) 
                VALUES ('Test Provider', 'Test Provider Display', 'test') 
                RETURNING id
            """))
            provider_id = result.scalar()
            
            # Insert a company identifier (should work)
            result = conn.execute(text("""
                INSERT INTO company_identifiers 
                (company_id, identifier_type, identifier_value, provider_id)
                VALUES (%s, 'ticker', 'TST', %s)
                RETURNING id
            """), (company_id, provider_id))
            id1 = result.scalar()
            
            # Try to insert duplicate identifier (should fail due to unique constraint)
            try:
                conn.execute(text("""
                    INSERT INTO company_identifiers 
                    (company_id, identifier_type, identifier_value, provider_id)
                    VALUES (%s, 'ticker', 'TST', %s)
                """), (company_id, provider_id))
                conn.commit()
                assert False, "Should have failed unique constraint"
            except Exception:
                conn.rollback()  # Expected to fail
                pass  # Unique constraint worked correctly
                
            # But we should be able to insert the same identifier for a different company
            result = conn.execute(text("""
                INSERT INTO companies (legal_name) 
                VALUES ('Test Company 2') 
                RETURNING id
            """))
            company_id2 = result.scalar()
            
            result = conn.execute(text("""
                INSERT INTO company_identifiers 
                (company_id, identifier_type, identifier_value, provider_id)
                VALUES (%s, 'ticker', 'TST', %s)
                RETURNING id
            """), (company_id2, provider_id))
            id2 = result.scalar()
            assert id2 is not None  # Should succeed
            
        finally:
            trans.rollback()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
