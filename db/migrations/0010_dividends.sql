-- 0010_dividends.sql
-- Dividend events per listing per provider.

CREATE TABLE dividends (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id UUID NOT NULL REFERENCES company_listings(id) ON DELETE CASCADE,
    provider_id UUID NOT NULL REFERENCES data_providers(id) ON DELETE RESTRICT,
    ex_dividend_date DATE,
    record_date DATE,
    payment_date DATE,
    amount NUMERIC(20, 10) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    source_id VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (listing_id, ex_dividend_date, provider_id, source_id),
    CONSTRAINT chk_dividends_amount CHECK (amount >= 0),
    CONSTRAINT chk_dividends_dates CHECK (
        ex_dividend_date IS NULL OR record_date IS NULL OR ex_dividend_date <= record_date
    )
);

CREATE INDEX idx_dividends_listing ON dividends(listing_id);
CREATE INDEX idx_dividends_ex_date ON dividends(ex_dividend_date);
CREATE INDEX idx_dividends_provider ON dividends(provider_id);

COMMENT ON TABLE dividends IS 'Dividend events per listing per provider. source_id strengthens uniqueness when ex_dividend_date is NULL.';