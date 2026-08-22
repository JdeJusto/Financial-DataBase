-- 0004_companies.sql
-- Core company entity. Identity is independent of ticker or exchange.
-- A company can have multiple identifiers and multiple listings.

CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_name VARCHAR(500) NOT NULL,
    country VARCHAR(100),
    sector VARCHAR(100),
    industry VARCHAR(100),
    currency VARCHAR(10) DEFAULT 'USD',
    website VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE companies IS 'Company entity independent of ticker or exchange. Ticker belongs to listings/identifiers.';