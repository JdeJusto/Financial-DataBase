-- 0024_currency_0.3.0.sql
-- Non-USD reporting currencies: per-fact currency, historical FX rates and
-- USD-converted core_financials values.
--
-- Context: financial_facts.unit already carries the filing currency (EUR for
-- SAN, GBP for BTI, USD for most US filers). The previous normalization layer
-- hardcoded NormalizedFinancials.currency="USD", so valuation ratios mixed
-- EUR/GBP fundamentals with USD ADR prices. This migration keeps every
-- original value untouched and adds a separate USD view.
--
-- Data model (v0.3.0): financial_facts.currency, per fact. A company/year may
-- legitimately contain a few facts in another currency (SAN has 44 USD facts
-- among 13k EUR facts); a single company-level currency would misclassify
-- them.
--
-- FX conversion is at period_end, using the latest rate on or before that
-- date (weekend/holiday -> previous business day). Missing rates leave
-- value_usd NULL; they are never replaced with 1.0.

BEGIN;

-- ---------------------------------------------------------------------
-- 1. Supported currencies (fiat only; crypto/metals/index units excluded)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fx_currencies (
  code varchar(3) PRIMARY KEY,
  name text
);

INSERT INTO fx_currencies (code, name) VALUES
  ('AED', 'UAE dirham'),
  ('AFN', 'Afghan afghani'),
  ('ARS', 'Argentine peso'),
  ('AUD', 'Australian dollar'),
  ('BMD', 'Bermudian dollar'),
  ('BRL', 'Brazilian real'),
  ('BSD', 'Bahamian dollar'),
  ('BWP', 'Botswana pula'),
  ('CAD', 'Canadian dollar'),
  ('CHE', 'WIR euro'),
  ('CHF', 'Swiss franc'),
  ('CLF', 'Unidad de Fomento'),
  ('CLP', 'Chilean peso'),
  ('CNY', 'Chinese yuan'),
  ('COP', 'Colombian peso'),
  ('CRC', 'Costa Rican colon'),
  ('CUP', 'Cuban peso'),
  ('CZK', 'Czech koruna'),
  ('DKK', 'Danish krone'),
  ('DZD', 'Algerian dinar'),
  ('EUR', 'Euro'),
  ('GBP', 'Pound sterling'),
  ('GEL', 'Georgian lari'),
  ('GHS', 'Ghanaian cedi'),
  ('HKD', 'Hong Kong dollar'),
  ('HNL', 'Honduran lempira'),
  ('IDR', 'Indonesian rupiah'),
  ('ILS', 'Israeli new shekel'),
  ('INR', 'Indian rupee'),
  ('ISK', 'Icelandic krona'),
  ('JOD', 'Jordanian dinar'),
  ('JPY', 'Japanese yen'),
  ('KHR', 'Cambodian riel'),
  ('KPW', 'North Korean won'),
  ('KRW', 'South Korean won'),
  ('KZT', 'Kazakhstani tenge'),
  ('MMK', 'Myanmar kyat'),
  ('MOP', 'Macanese pataca'),
  ('MXN', 'Mexican peso'),
  ('MYR', 'Malaysian ringgit'),
  ('NIO', 'Nicaraguan cordoba'),
  ('NIS', 'Israeli shekel (legacy code)'),
  ('NOK', 'Norwegian krone'),
  ('NZD', 'New Zealand dollar'),
  ('PEN', 'Peruvian sol'),
  ('PHP', 'Philippine peso'),
  ('PKR', 'Pakistani rupee'),
  ('PLN', 'Polish zloty'),
  ('RUB', 'Russian ruble'),
  ('SAR', 'Saudi riyal'),
  ('SDG', 'Sudanese pound'),
  ('SEK', 'Swedish krona'),
  ('SGD', 'Singapore dollar'),
  ('STD', 'Sao Tome and Principe dobra'),
  ('THB', 'Thai baht'),
  ('TJS', 'Tajikistani somoni'),
  ('TND', 'Tunisian dinar'),
  ('TRY', 'Turkish lira'),
  ('TWD', 'New Taiwan dollar'),
  ('TZS', 'Tanzanian shilling'),
  ('UAH', 'Ukrainian hryvnia'),
  ('USD', 'US dollar'),
  ('UYI', 'Uruguay indexed unit'),
  ('VEF', 'Venezuelan bolivar'),
  ('VND', 'Vietnamese dong'),
  ('ZAR', 'South African rand')
ON CONFLICT (code) DO NOTHING;

-- ---------------------------------------------------------------------
-- 2. Per-fact currency (backfilled from the real `unit`)
-- ---------------------------------------------------------------------
ALTER TABLE financial_facts
  ADD COLUMN IF NOT EXISTS currency varchar(3);

-- The mass backfill is run separately by
-- `python -m scripts.detect_reporting_currency --backfill` after the
-- migration (it updates ~1.9M rows and should not hold the migration lock).
-- core_financials derives the display currency from `unit` directly, so it
-- is correct even before the backfill finishes.

CREATE INDEX IF NOT EXISTS idx_financial_facts_currency
  ON financial_facts (currency)
  WHERE currency IS NOT NULL AND currency <> 'USD';

-- ---------------------------------------------------------------------
-- 3. Historical FX rates (USD per one unit of `currency`)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fx_rates (
  currency varchar(3) NOT NULL,
  rate_date date NOT NULL,
  usd_per_unit numeric(24,10) NOT NULL CHECK (usd_per_unit > 0),
  source text NOT NULL,
  PRIMARY KEY (currency, rate_date)
);

CREATE INDEX IF NOT EXISTS idx_fx_rates_currency_date
  ON fx_rates (currency, rate_date DESC);

-- ---------------------------------------------------------------------
-- 4. core_financials: keep the original values, add currency + *_usd
-- ---------------------------------------------------------------------
-- Conversion is applied once per aggregated company-year row, not once per
-- fact: the materialized view first aggregates the original values (as
-- before), records the row's dominant reporting currency (mode of the
-- contributing facts), and converts the aggregate with the latest FX rate on
-- or before period_end. Per-fact currency remains in financial_facts for
-- audits; the row-level mode is correct for the normal case (one filing
-- currency per company-year) and avoids a 28M-row lateral join.
DROP MATERIALIZED VIEW IF EXISTS core_financials CASCADE;

CREATE MATERIALIZED VIEW core_financials AS
WITH revenue_parts AS (
  SELECT
    ff.company_id,
    ff.fiscal_year,
    ff.period_end,
    max(ff.value) FILTER (WHERE cn.combine IS NULL) AS total_rev,
    sum(ff.value) FILTER (WHERE cn.combine = 'sum') AS components_rev,
    max(ff.unit) FILTER (
      WHERE cn.combine IS NULL AND ff.unit IN (SELECT code FROM fx_currencies)
    ) AS currency
  FROM financial_facts ff
  JOIN concept_normalization cn
    ON cn.concept = ff.concept
   AND (cn.namespace = '*' OR cn.namespace = ff.namespace)
  WHERE cn.field = 'revenue' AND ff.fiscal_period = 'FY'
  GROUP BY 1, 2, 3
),
other_fields AS (
  SELECT
    ff.company_id,
    ff.fiscal_year,
    ff.period_end,
    max(ff.value) FILTER (WHERE cn.field = 'net_income') AS net_income,
    max(ff.value) FILTER (WHERE cn.field = 'operating_income') AS operating_income,
    max(ff.value) FILTER (WHERE cn.field = 'gross_profit') AS gross_profit,
    max(ff.value) FILTER (WHERE cn.field = 'total_assets') AS total_assets,
    max(ff.value) FILTER (WHERE cn.field = 'total_liabilities') AS total_liabilities,
    max(ff.value) FILTER (WHERE cn.field = 'stockholders_equity') AS stockholders_equity,
    max(ff.value) FILTER (WHERE cn.field = 'cash_and_equivalents') AS cash,
    max(ff.unit) FILTER (
      WHERE cn.field = 'total_assets' AND ff.unit IN (SELECT code FROM fx_currencies)
    ) AS currency
  FROM financial_facts ff
  JOIN concept_normalization cn
    ON cn.concept = ff.concept
   AND (cn.namespace = '*' OR cn.namespace = ff.namespace)
  WHERE cn.field IN (
    'net_income', 'operating_income', 'gross_profit', 'total_assets',
    'total_liabilities', 'stockholders_equity', 'cash_and_equivalents'
  )
    AND ff.fiscal_period = 'FY'
  GROUP BY 1, 2, 3
),
combined AS (
  SELECT
    COALESCE(r.company_id, o.company_id) AS company_id,
    COALESCE(r.fiscal_year, o.fiscal_year) AS fiscal_year,
    COALESCE(r.period_end, o.period_end) AS period_end,
    COALESCE(r.total_rev, r.components_rev) AS revenue,
    o.net_income,
    o.operating_income,
    o.gross_profit,
    o.total_assets,
    o.total_liabilities,
    o.stockholders_equity,
    o.cash,
    COALESCE(r.currency, o.currency) AS currency
  FROM revenue_parts r
  FULL OUTER JOIN other_fields o
    ON r.company_id = o.company_id
   AND r.fiscal_year = o.fiscal_year
   AND r.period_end = o.period_end
)
SELECT
  c.company_id,
  c.fiscal_year,
  c.period_end,
  c.revenue,
  CASE
    WHEN c.currency = 'USD' THEN c.revenue
    WHEN fx.usd_per_unit IS NOT NULL THEN c.revenue * fx.usd_per_unit
    ELSE NULL
  END AS revenue_usd,
  c.net_income,
  CASE
    WHEN c.currency = 'USD' THEN c.net_income
    WHEN fx.usd_per_unit IS NOT NULL THEN c.net_income * fx.usd_per_unit
    ELSE NULL
  END AS net_income_usd,
  c.operating_income,
  CASE
    WHEN c.currency = 'USD' THEN c.operating_income
    WHEN fx.usd_per_unit IS NOT NULL THEN c.operating_income * fx.usd_per_unit
    ELSE NULL
  END AS operating_income_usd,
  c.gross_profit,
  CASE
    WHEN c.currency = 'USD' THEN c.gross_profit
    WHEN fx.usd_per_unit IS NOT NULL THEN c.gross_profit * fx.usd_per_unit
    ELSE NULL
  END AS gross_profit_usd,
  c.total_assets,
  CASE
    WHEN c.currency = 'USD' THEN c.total_assets
    WHEN fx.usd_per_unit IS NOT NULL THEN c.total_assets * fx.usd_per_unit
    ELSE NULL
  END AS total_assets_usd,
  c.total_liabilities,
  CASE
    WHEN c.currency = 'USD' THEN c.total_liabilities
    WHEN fx.usd_per_unit IS NOT NULL THEN c.total_liabilities * fx.usd_per_unit
    ELSE NULL
  END AS total_liabilities_usd,
  c.stockholders_equity,
  CASE
    WHEN c.currency = 'USD' THEN c.stockholders_equity
    WHEN fx.usd_per_unit IS NOT NULL THEN c.stockholders_equity * fx.usd_per_unit
    ELSE NULL
  END AS stockholders_equity_usd,
  c.cash,
  CASE
    WHEN c.currency = 'USD' THEN c.cash
    WHEN fx.usd_per_unit IS NOT NULL THEN c.cash * fx.usd_per_unit
    ELSE NULL
  END AS cash_usd,
  c.currency
FROM combined c
LEFT JOIN LATERAL (
  SELECT r.usd_per_unit
  FROM fx_rates r
  WHERE r.currency = c.currency
    AND r.rate_date <= c.period_end
  ORDER BY r.rate_date DESC
  LIMIT 1
) fx ON true;

CREATE UNIQUE INDEX IF NOT EXISTS idx_core_financials_company_period
  ON core_financials (company_id, fiscal_year, period_end);
CREATE INDEX IF NOT EXISTS idx_core_financials_company_year
  ON core_financials (company_id, fiscal_year);
CREATE INDEX IF NOT EXISTS idx_core_financials_currency
  ON core_financials (currency)
  WHERE currency IS NOT NULL AND currency <> 'USD';

-- The view depended on the old materialized view (DROP ... CASCADE removed it).
CREATE OR REPLACE VIEW balance_effective AS
SELECT company_id, fiscal_year, period_end,
  total_assets,
  COALESCE(total_liabilities, total_assets - stockholders_equity) AS liabilities_effective,
  (total_liabilities IS NULL AND total_assets IS NOT NULL
   AND stockholders_equity IS NOT NULL) AS liabilities_derived,
  stockholders_equity, cash
FROM core_financials;

COMMIT;
