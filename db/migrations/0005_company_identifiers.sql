-- 0005_company_identifiers.sql
-- Company identifiers: ticker, CIK, ISIN, LEI, provider-specific IDs
-- Uniqueness is per company + identifier_type + provider.
-- Ticker is NOT globally unique - same ticker can exist on different exchanges/providers.

CREATE TABLE company_identifiers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    identifier_type VARCHAR(50) NOT NULL, -- 'ticker', 'cik', 'isin', 'lei', 'figi', etc.
    identifier_value VARCHAR(255) NOT NULL,
    provider_id UUID REFERENCES data_providers(id) ON DELETE SET NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    valid_from DATE,
    valid_to DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (company_id, identifier_type, provider_id, identifier_value)
);

CREATE INDEX idx_company_identifiers_company ON company_identifiers(company_id);
CREATE INDEX idx_company_identifiers_type_value ON company_identifiers(identifier_type, identifier_value);
CREATE INDEX idx_company_identifiers_provider ON company_identifiers(provider_id);

COMMENT ON TABLE company_identifiers IS 'External identifiers for companies. Uniqueness is per company+type+provider. Ticker not globally unique.';