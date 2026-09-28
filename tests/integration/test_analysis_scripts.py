"""Integration tests for SQL analysis scripts against SEC sample data."""

import pytest


@pytest.fixture(autouse=True)
def require_apple_and_microsoft_facts(db_connection):
    """Skip data-dependent checks when the isolated DB has no SEC fixture data."""
    for cik in ("0000320193", "0000789019"):
        result = db_connection.execute_script(
            "scripts/analysis/company_overview.sql", {"cik": cik}
        )
        if not result or not result[0]["total_facts"]:
            pytest.skip(
                "SQL analysis checks require AAPL and MSFT SEC facts in the test DB"
            )


def test_company_overview_script(db_connection):
    """Test company_overview.sql script returns expected columns."""
    result = db_connection.execute_script("scripts/analysis/company_overview.sql", {"cik": "0000320193"})

    # Should return exactly one row for Apple
    assert len(result) == 1
    row = result[0]

    # Check expected columns are present
    expected_columns = {
        'legal_name', 'sector', 'industry', 'country',
        'earliest_fiscal_year', 'latest_fiscal_year',
        'total_facts', 'total_filings'
    }
    assert set(row.keys()) == expected_columns

    # Check values are reasonable
    assert row['legal_name'] == 'Apple Inc.'
    assert row['country'] == 'USA'
    assert row['earliest_fiscal_year'] is not None
    assert row['latest_fiscal_year'] is not None
    assert row['earliest_fiscal_year'] <= row['latest_fiscal_year']
    assert row['total_facts'] > 0
    assert row['total_filings'] > 0


def test_financial_series_script(db_connection):
    """Test financial_series.sql script returns expected columns and data."""
    result = db_connection.execute_script("scripts/analysis/financial_series.sql", {"cik": "0000320193"})

    # Should return multiple rows (one per fiscal year)
    assert len(result) > 5  # Apple has data for many years

    # Check first row has expected columns
    first_row = result[0]
    expected_columns = {
        'fiscal_year', 'revenue', 'net_income', 'total_assets',
        'stockholders_equity', 'total_liabilities', 'operating_cash_flow',
        'capex', 'free_cash_flow', 'revenue_growth_pct',
        'net_income_growth_pct', 'total_assets_growth_pct',
        'net_margin_pct', 'operating_margin_pct', 'fcf_margin_pct'
    }
    assert set(first_row.keys()) == expected_columns

    # Check that fiscal years are ordered
    fiscal_years = [row['fiscal_year'] for row in result]
    assert fiscal_years == sorted(fiscal_years)


def test_ratios_advanced_script(db_connection):
    """Test ratios_advanced.sql script returns expected columns."""
    result = db_connection.execute_script("scripts/analysis/ratios_advanced.sql", {"cik": "0000320193"})

    # Should return multiple rows
    assert len(result) > 0

    # Check first row has expected columns
    first_row = result[0]
    expected_columns = {
        'fiscal_year', 'revenue', 'net_income', 'total_assets',
        'stockholders_equity', 'total_liabilities', 'roe_pct',
        'roa_pct', 'net_margin_pct', 'debt_to_equity',
        'debt_to_assets', 'current_ratio', 'market_cap', 'pe_ratio'
    }
    assert set(first_row.keys()) == expected_columns

    # Check that ratios are calculated correctly for first row
    row = first_row
    if row['net_income'] is not None and row['stockholders_equity'] is not None and row['stockholders_equity'] != 0:
        expected_roe = (row['net_income'] / row['stockholders_equity']) * 100
        assert abs(row['roe_pct'] - expected_roe) < 0.01  # Allow small floating point differences


def test_compare_companies_script(db_connection):
    """Test compare_companies.sql script works with multiple CIKs."""
    # Test with Apple and Microsoft
    result = db_connection.execute_script(
        "scripts/analysis/compare_companies.sql",
        {"ciks": ["0000320193", "0000789019"]}
    )

    # Should return exactly two rows (one per company)
    assert len(result) == 2

    # Check that we have data for both companies
    ciks_in_result = {row['cik'] for row in result}
    assert ciks_in_result == {"0000320193", "0000789019"}

    # Check expected columns are present
    first_row = result[0]
    expected_columns = {
        'cik', 'latest_fiscal_year', 'revenue', 'net_income',
        'roe_pct', 'net_margin_pct', 'debt_to_equity', 'revenue_growth_pct'
    }
    assert set(first_row.keys()) == expected_columns

    # Check that revenue is ordered descending (NULLS LAST)
    revenues = [row['revenue'] for row in result if row['revenue'] is not None]
    assert revenues == sorted(revenues, reverse=True)


def test_scripts_handle_invalid_cik_gracefully(db_connection):
    """Test that scripts handle invalid or non-existent CIKs gracefully."""
    # Test with a CIK that likely doesn't exist
    result = db_connection.execute_script(
        "scripts/analysis/company_overview.sql",
        {"cik": "9999999999"}
    )

    # Should return empty results or NULL values, not error
    # Depending on implementation, might return 0 rows or rows with NULLs
    assert isinstance(result, list)  # Should not raise exception


if __name__ == "__main__":
    pytest.main([__file__])
