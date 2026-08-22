-- 0002_data_providers.sql
-- External data providers (SEC, AlphaVantage, Yahoo, Polygon, etc.)
-- This is the source of truth for provider identity.

CREATE TABLE data_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(255),
    type VARCHAR(50) NOT NULL, -- 'sec', 'price', 'fundamental', etc.
    base_url VARCHAR(500),
    rate_limit_per_second NUMERIC(10, 2),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE data_providers IS 'External data providers. All provider references in other tables should use provider_id FK.';