-- 0003_exchanges.sql
-- Stock exchanges where companies list

CREATE TABLE exchanges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) NOT NULL UNIQUE, -- e.g., 'NASDAQ', 'NYSE', 'LSE'
    name VARCHAR(255) NOT NULL,
    country VARCHAR(100),
    timezone VARCHAR(50),
    currency VARCHAR(10) DEFAULT 'USD',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE exchanges IS 'Stock exchanges where companies list.';