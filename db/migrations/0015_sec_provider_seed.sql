-- 0015_sec_provider_seed.sql
-- Seed SEC EDGAR provider and exchanges for SEC data ingestion.

-- Insert SEC EDGAR provider if not exists
INSERT INTO data_providers (name, type, display_name, base_url, rate_limit_per_second, is_active)
VALUES ('SEC EDGAR', 'sec', 'SEC EDGAR', 'https://www.sec.gov', 10.0, TRUE)
ON CONFLICT (name) DO NOTHING;

-- Seed exchanges commonly used by SEC companies
-- These match the ExchangeMapping table in the SEC provider

-- NASDAQ
INSERT INTO exchanges (code, name, country, timezone, currency)
VALUES ('NASDAQ', 'NASDAQ Stock Market', 'USA', 'America/New_York', 'USD')
ON CONFLICT (code) DO NOTHING;

-- NYSE
INSERT INTO exchanges (code, name, country, timezone, currency)
VALUES ('NYSE', 'New York Stock Exchange', 'USA', 'America/New_York', 'USD')
ON CONFLICT (code) DO NOTHING;

-- NYSE American (formerly AMEX)
INSERT INTO exchanges (code, name, country, timezone, currency)
VALUES ('NYSEAMERICAN', 'NYSE American', 'USA', 'America/New_York', 'USD')
ON CONFLICT (code) DO NOTHING;

-- NYSE Arca
INSERT INTO exchanges (code, name, country, timezone, currency)
VALUES ('NYSEARCA', 'NYSE Arca', 'USA', 'America/New_York', 'USD')
ON CONFLICT (code) DO NOTHING;

-- BATS (now Cboe)
INSERT INTO exchanges (code, name, country, timezone, currency)
VALUES ('BATS', 'BATS Exchange', 'USA', 'America/New_York', 'USD')
ON CONFLICT (code) DO NOTHING;

-- OTC Markets
INSERT INTO exchanges (code, name, country, timezone, currency)
VALUES ('OTC', 'OTC Markets', 'USA', 'America/New_York', 'USD')
ON CONFLICT (code) DO NOTHING;

-- OTCQB
INSERT INTO exchanges (code, name, country, timezone, currency)
VALUES ('OTCQB', 'OTCQB Market', 'USA', 'America/New_York', 'USD')
ON CONFLICT (code) DO NOTHING;

-- OTCQX
INSERT INTO exchanges (code, name, country, timezone, currency)
VALUES ('OTCQX', 'OTCQX Market', 'USA', 'America/New_York', 'USD')
ON CONFLICT (code) DO NOTHING;

-- Pink Sheets
INSERT INTO exchanges (code, name, country, timezone, currency)
VALUES ('PINK', 'Pink Sheets', 'USA', 'America/New_York', 'USD')
ON CONFLICT (code) DO NOTHING;

COMMENT ON TABLE data_providers IS 'External data providers. SEC EDGAR is the primary regulatory data source.';
COMMENT ON TABLE exchanges IS 'Stock exchanges. Seeded with SEC-relevant exchanges for company listings.';