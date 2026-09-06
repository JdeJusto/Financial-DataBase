# Reusable SQL Analysis Scripts

This document describes the reusable SQL analysis scripts available in the `scripts/analysis/` directory. These scripts are designed to be parameterized and reusable for financial analysis of companies in the database.

## Available Scripts

### 1. company_overview.sql

Returns general company information for a given CIK.

**Parameters:**
- `:cik` - The CIK of the company to analyze (e.g., '0000320193' for Apple)

**Returns:**
- `legal_name` - Company's legal name
- `sector` - Business sector
- `industry` - Specific industry
- `country` - Country of incorporation
- `earliest_fiscal_year` - First year with available data
- `latest_fiscal_year` - Most recent year with available data
- `total_facts` - Total number of financial facts in the database
- `total_filings` - Total number of SEC filings

**Usage:**
```sql
\set cik '0000320193'
\i scripts/analysis/company_overview.sql
```

### 2. financial_series.sql

Returns yearly financial time series data with growth rates and margins.

**Parameters:**
- `:cik` - The CIK of the company to analyze

**Returns:**
- `fiscal_year` - The fiscal year
- `revenue` - Total revenue
- `net_income` - Net income/loss
- `total_assets` - Total assets
- `stockholders_equity` - Shareholders' equity
- `total_liabilities` - Total liabilities
- `operating_cash_flow` - Cash flow from operations
- `capex` - Capital expenditures
- `free_cash_flow` - Operating cash flow minus capital expenditures
- `revenue_growth_pct` - Year-over-year revenue growth percentage
- `net_income_growth_pct` - Year-over-year net income growth percentage
- `total_assets_growth_pct` - Year-over-year total assets growth percentage
- `net_margin_pct` - Net income as percentage of revenue
- `operating_margin_pct` - Operating cash flow as percentage of revenue
- `fcf_margin_pct` - Free cash flow as percentage of revenue

**Usage:**
```sql
\set cik '0000320193'
\i scripts/analysis/financial_series.sql
```

### 3. ratios_advanced.sql

Returns advanced financial ratios including profitability, leverage, and valuation metrics.

**Parameters:**
- `:cik` - The CIK of the company to analyze

**Returns:**
- `fiscal_year` - The fiscal year
- `revenue` - Total revenue
- `net_income` - Net income/loss
- `total_assets` - Total assets
- `stockholders_equity` - Shareholders' equity
- `total_liabilities` - Total liabilities
- `roe_pct` - Return on Equity (Net Income / Shareholders' Equity)
- `roa_pct` - Return on Assets (Net Income / Total Assets)
- `net_margin_pct` - Net Profit Margin (Net Income / Revenue)
- `debt_to_equity` - Debt to Equity Ratio (Total Liabilities / Shareholders' Equity)
- `debt_to_assets` - Debt to Assets Ratio (Total Liabilities / Total Assets)
- `current_ratio` - Current Ratio (Current Assets / Current Liabilities)
- `market_cap` - Market Capitalization (Share Price × Shares Outstanding)
- `pe_ratio` - Price to Earnings Ratio (Market Cap / Net Income)

**Note:** Valuation ratios (market_cap, pe_ratio) require stock price data to be available in the prices table.

**Usage:**
```sql
\set cik '0000320193'
\i scripts/analysis/ratios_advanced.sql
```

### 4. compare_companies.sql

Compares key financial metrics across multiple companies for their latest fiscal year.

**Parameters:**
- `:ciks` - Array of CIKs to compare (e.g., ARRAY['0000320193', '0000789019'] for Apple and Microsoft)

**Returns:**
- `cik` - The CIK of the company
- `latest_fiscal_year` - Most recent fiscal year with data
- `revenue` - Total revenue for latest year
- `net_income` - Net income for latest year
- `roe_pct` - Return on Equity for latest year
- `net_margin_pct` - Net profit margin for latest year
- `debt_to_equity` - Debt to equity ratio for latest year
- `revenue_growth_pct` - Year-over-year revenue growth percentage

**Usage:**
```sql
\set ciks '{"0000320193","0000789019"}'
\i scripts/analysis/compare_companies.sql
```

## Design Principles

All scripts follow these design principles:

1. **Parameterized** - Use PostgreSQL parameter syntax (:param_name) for safe substitution
2. **Idempotent** - Can be run multiple times without side effects
3. **Well-documented** - Clear comments explaining each section
4. **Efficient** - Use CTEs and proper joins for optimal performance
5. **Robust** - Handle NULL values and edge cases appropriately
6. **Readable** - Formatted for clarity and maintainability

## Requirements

- PostgreSQL 9.5+ (for CTE support)
- Financial database schema with companies, financial_facts, filings, etc.
- For valuation ratios: stock price data in the prices table from Yahoo Finance provider

## Examples

### Apple Inc. (CIK: 0000320193) Overview
```sql
\set cik '0000320193'
\i scripts/analysis/company_overview.sql
```

### Microsoft Corporation (CIK: 0000789019) Financial Series
```sql
\set cik '0000789019'
\i scripts/analysis/financial_series.sql
```

### Compare Apple and Microsoft
```sql
\set ciks '{"0000320193","0000789019"}'
\i scripts/analysis/compare_companies.sql
```

## Maintenance

When modifying these scripts:
1. Keep backward compatibility with existing parameter names
2. Add clear comments for complex logic
3. Test with known CIKs (Apple: 0000320193, Microsoft: 0000789019)
4. Ensure proper handling of edge cases (NULL values, zero denominators)