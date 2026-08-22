-- 0009_prices.sql
-- Historical market prices per listing per provider.
-- Prices belong to a listing (company+exchange+ticker), not directly to company.

CREATE TABLE prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id UUID NOT NULL REFERENCES company_listings(id) ON DELETE CASCADE,
    provider_id UUID NOT NULL REFERENCES data_providers(id) ON DELETE RESTRICT,
    price_date DATE NOT NULL,
    open NUMERIC(20, 6) NOT NULL,
    high NUMERIC(20, 6) NOT NULL,
    low NUMERIC(20, 6) NOT NULL,
    close NUMERIC(20, 6) NOT NULL,
    adjusted_close NUMERIC(20, 6),
    volume BIGINT NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    source_id VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (listing_id, price_date, provider_id)
);

CREATE INDEX idx_prices_listing ON prices(listing_id);
CREATE INDEX idx_prices_date ON prices(price_date);
CREATE INDEX idx_prices_provider ON prices(provider_id);
CREATE INDEX idx_prices_listing_date ON prices(listing_id, price_date);

COMMENT ON TABLE prices IS 'Historical prices per listing per provider. Uses NUMERIC for precision. Uniqueness per listing+date+provider.';