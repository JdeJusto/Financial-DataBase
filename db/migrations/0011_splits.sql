-- 0011_splits.sql
-- Stock split events per listing per provider.

CREATE TABLE splits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id UUID NOT NULL REFERENCES company_listings(id) ON DELETE CASCADE,
    provider_id UUID NOT NULL REFERENCES data_providers(id) ON DELETE RESTRICT,
    execution_date DATE NOT NULL,
    numerator INTEGER NOT NULL,
    denominator INTEGER NOT NULL,
    source_id VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (listing_id, execution_date, provider_id, source_id),
    CONSTRAINT chk_splits_positive CHECK (numerator > 0 AND denominator > 0)
);

CREATE INDEX idx_splits_listing ON splits(listing_id);
CREATE INDEX idx_splits_date ON splits(execution_date);
CREATE INDEX idx_splits_provider ON splits(provider_id);

COMMENT ON TABLE splits IS 'Stock splits per listing per provider. numerator/denominator e.g., 2-for-1 = 2/1.';