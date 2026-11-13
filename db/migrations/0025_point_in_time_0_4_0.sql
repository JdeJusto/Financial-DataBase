-- 0025_point_in_time_0.4.0.sql
-- Point-in-time fundamentals and historical index membership.
--
-- Context: financial_facts.filing_date already exists, is NOT NULL and is
-- fully populated (76.2M rows, 2009-04-15..). It is the date the fact became
-- public, i.e. the point-in-time key. This migration does NOT add a redundant
-- column: it documents the semantics, adds the composite index used by
-- "facts known on date D" queries, and adds the historical S&P 500 table.
--
-- A point-in-time read is:
--   SELECT DISTINCT ON (concept) concept, value, filing_date
--   FROM financial_facts
--   WHERE company_id = $1
--     AND fiscal_year = $2
--     AND filing_date <= $as_of
--     AND period_end <= $as_of
--   ORDER BY concept, filing_date DESC;
-- The DISTINCT ON keeps the latest version known at the as-of date, so a
-- restatement filed after the as-of date is ignored.
--
-- Historical membership: `sp500_constituents` stores half-open intervals
-- [start_date, end_date). end_date IS NULL means "still a member". company_id
-- is nullable because delisted constituents often have no row in `companies`
-- (SEC ingestion only covers filers still present in the database).

BEGIN;

-- ---------------------------------------------------------------------
-- 1. Point-in-time index
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_financial_facts_pit
ON financial_facts (company_id, fiscal_year, filing_date DESC, period_end);

COMMENT ON COLUMN financial_facts.filing_date IS
  'Date the fact became public (SEC filing date). Point-in-time key: a fact is '
  'known at as_of iff filing_date <= as_of. Restatements keep later dates.';

-- ---------------------------------------------------------------------
-- 2. Historical S&P 500 membership
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sp500_constituents (
  ticker      text        NOT NULL,
  start_date  date        NOT NULL,
  end_date    date,
  company_id  uuid        REFERENCES companies(id) ON DELETE SET NULL,
  source      text        NOT NULL DEFAULT 'fja05680',
  loaded_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (ticker, start_date),
  CONSTRAINT sp500_constituents_valid_interval
    CHECK (end_date IS NULL OR end_date > start_date)
);

CREATE INDEX IF NOT EXISTS idx_sp500_constituents_dates
ON sp500_constituents (start_date, end_date);

CREATE INDEX IF NOT EXISTS idx_sp500_constituents_company
ON sp500_constituents (company_id)
WHERE company_id IS NOT NULL;

COMMENT ON TABLE sp500_constituents IS
  'Historical S&P 500 membership as half-open intervals [start_date, end_date). '
  'end_date IS NULL means the ticker is still a member. company_id is nullable '
  'for delisted constituents absent from the SEC universe.';

-- ---------------------------------------------------------------------
-- 3. Delisted flag (documentation / future use)
-- ---------------------------------------------------------------------
ALTER TABLE companies ADD COLUMN IF NOT EXISTS delisted_at date;

CREATE INDEX IF NOT EXISTS idx_companies_delisted
ON companies (delisted_at)
WHERE delisted_at IS NOT NULL;

COMMENT ON COLUMN companies.delisted_at IS
  'Date the company stopped trading, when known. FDB has no historical '
  'delisted price coverage; the column records the fact for survivorship '
  'reporting, not for backtest pricing.';

COMMIT;
