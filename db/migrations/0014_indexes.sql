-- 0014_indexes.sql
-- Additional indexes for common query patterns.
-- Base indexes created in individual table migrations.
-- This migration adds composite/covering indexes for specific query patterns.

-- Companies
CREATE INDEX idx_companies_name ON companies(legal_name);
CREATE INDEX idx_companies_country ON companies(country);

-- Company identifiers - for lookup by ticker/value
CREATE INDEX idx_company_identifiers_lookup ON company_identifiers(identifier_type, identifier_value, provider_id);

-- Filings - common query patterns
CREATE INDEX idx_filings_company_fiscal ON filings(company_id, fiscal_year, fiscal_period);

-- Financial facts - critical query patterns
CREATE INDEX idx_financial_facts_company_concept_fiscal ON financial_facts(company_id, concept, fiscal_year DESC, fiscal_period DESC);
CREATE INDEX idx_financial_facts_filing_concept ON financial_facts(filing_id, concept);

-- Prices - time series queries
CREATE INDEX idx_prices_listing_date_desc ON prices(listing_id, price_date DESC);
CREATE INDEX idx_prices_provider_date ON prices(provider_id, price_date);

-- Dividends/Splits
CREATE INDEX idx_dividends_listing_date ON dividends(listing_id, ex_dividend_date DESC);
CREATE INDEX idx_splits_listing_date ON splits(listing_id, execution_date DESC);

-- Import runs
CREATE INDEX idx_import_runs_provider_pipeline ON import_runs(provider_id, pipeline);

COMMENT ON TABLE financial_facts IS 'Normalized financial observations. period_start NULL = instant fact (balance sheet), NOT NULL = duration fact (income statement). Restatements coexist via unique constraint on source/filing.';