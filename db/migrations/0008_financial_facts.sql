-- 0008_financial_facts.sql
-- Normalized financial facts with full provenance.
-- Supports both instant (balance sheet) and duration (income statement) facts.
-- Restatements coexist via filing/source identity.

CREATE TABLE financial_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    filing_id UUID REFERENCES filings(id) ON DELETE SET NULL,
    provider_id UUID NOT NULL REFERENCES data_providers(id) ON DELETE RESTRICT,
    concept VARCHAR(255) NOT NULL, -- e.g., 'Revenue', 'Assets', 'NetIncomeLoss'
    value NUMERIC(30, 10) NOT NULL,
    unit VARCHAR(50) NOT NULL, -- 'USD', 'EUR', 'shares', 'USD/share'
    period_start DATE, -- NULL for instant facts, set for duration facts
    period_end DATE NOT NULL,
    fiscal_year INTEGER NOT NULL,
    fiscal_period VARCHAR(20) NOT NULL, -- 'FY', 'Q1', 'Q2', 'Q3', 'H1', 'H2'
    form VARCHAR(50), -- '10-K', '10-Q', etc.
    source_id VARCHAR(255), -- provider-specific fact identifier
    filing_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Uniqueness: one observation per company+concept+period+filing+source
    UNIQUE (company_id, concept, period_start, period_end, filing_id, source_id),
    -- Check constraint: period consistency
    CONSTRAINT chk_financial_facts_period CHECK (
        period_start IS NULL OR period_start <= period_end
    )
);

CREATE INDEX idx_financial_facts_company ON financial_facts(company_id);
CREATE INDEX idx_financial_facts_concept ON financial_facts(concept);
CREATE INDEX idx_financial_facts_period ON financial_facts(period_start, period_end);
CREATE INDEX idx_financial_facts_fiscal ON financial_facts(fiscal_year, fiscal_period);
CREATE INDEX idx_financial_facts_provider ON financial_facts(provider_id);
CREATE INDEX idx_financial_facts_filing ON financial_facts(filing_id);
CREATE INDEX idx_financial_facts_company_concept ON financial_facts(company_id, concept);

COMMENT ON TABLE financial_facts IS 'Normalized financial observations. period_start NULL = instant fact (balance sheet), NOT NULL = duration fact (income statement). Restatements coexist via unique constraint on source/filing.';