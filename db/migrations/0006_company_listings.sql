-- 0006_company_listings.sql
-- Company listings on exchanges with historical validity.
-- A company can have multiple listings over time (ticker changes, exchange moves, share classes).
-- Uses exclusion constraint to prevent overlapping validity periods for same company+exchange+share_class.

CREATE TABLE company_listings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    exchange_id UUID NOT NULL REFERENCES exchanges(id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    share_class VARCHAR(20), -- e.g., 'A', 'B', 'C' for multi-class shares
    listing_date DATE,
    delisting_date DATE,
    is_primary BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (company_id, exchange_id, share_class, listing_date)
);

-- Exclusion constraint: no overlapping active periods for same company+exchange+share_class
ALTER TABLE company_listings
    ADD CONSTRAINT no_overlapping_listings
    EXCLUDE USING gist (
        company_id WITH =,
        exchange_id WITH =,
        share_class WITH =,
        daterange(listing_date, delisting_date, '[]') WITH &&
    )
    WHERE (listing_date IS NOT NULL AND delisting_date IS NOT NULL);

CREATE INDEX idx_company_listings_company ON company_listings(company_id);
CREATE INDEX idx_company_listings_exchange ON company_listings(exchange_id);
CREATE INDEX idx_company_listings_ticker ON company_listings(ticker);
CREATE INDEX idx_company_listings_active ON company_listings(is_active) WHERE is_active;

COMMENT ON TABLE company_listings IS 'Company listings on exchanges with historical validity. Supports ticker changes, delistings, share classes.';