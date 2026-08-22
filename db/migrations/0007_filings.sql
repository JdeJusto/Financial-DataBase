-- 0007_filings.sql
-- Source documents/filings from providers (SEC EDGAR, etc.)
-- A filing is a source document that contains financial data.

CREATE TABLE filings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    provider_id UUID NOT NULL REFERENCES data_providers(id) ON DELETE RESTRICT,
    form VARCHAR(50) NOT NULL, -- e.g., '10-K', '10-Q', '8-K', '20-F'
    accession_number VARCHAR(255) NOT NULL,
    filing_date DATE NOT NULL,
    period_start DATE, -- nullable for instant/point-in-time filings
    period_end DATE NOT NULL,
    fiscal_year INTEGER,
    fiscal_period VARCHAR(20), -- 'FY', 'Q1', 'Q2', 'Q3', 'H1', 'H2'
    filing_url VARCHAR(500),
    raw_document_id UUID, -- FK to raw_documents (added later)
    is_amended BOOLEAN DEFAULT FALSE,
    amended_by_filing_id UUID REFERENCES filings(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider_id, accession_number)
);

CREATE INDEX idx_filings_company ON filings(company_id);
CREATE INDEX idx_filings_provider ON filings(provider_id);
CREATE INDEX idx_filings_form ON filings(form);
CREATE INDEX idx_filings_filing_date ON filings(filing_date);
CREATE INDEX idx_filings_period ON filings(period_start, period_end);
CREATE INDEX idx_filings_fiscal ON filings(fiscal_year, fiscal_period);

COMMENT ON TABLE filings IS 'Source filings/documents from providers. period_start nullable for instant facts. Accession unique per provider.';