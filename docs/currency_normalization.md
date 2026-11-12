# Currency normalization (v0.3.0)

Status: implemented in migration `0024_currency_0_3_0.sql`, applied on
2026-11-12. `financial_facts.value` is never modified; USD values are a
separate, derived column.

## Problem

SEC XBRL filings report monetary facts in the filing currency. The
`financial_facts.unit` column already carried the real unit (`EUR` for Sanofi,
`GBP` for British American Tobacco, `USD` for most US filers), but VI's
normalization layer hardcoded `NormalizedFinancials.currency = "USD"`. The
NYSE ADR price is USD, so P/E, P/B and FCF yield mixed currencies for non-USD
reporters.

Measured scope (2026-11-12):

| Metric | Value |
|---|---:|
| `financial_facts` rows with a non-USD ISO currency | 1,919,616 |
| Companies with at least one non-USD fact | 1,872 |
| `core_financials` rows belonging to those companies | 36,561 |
| `core_financials` rows total | 336,196 |

SAN has 13,070 EUR facts plus 44 USD and 2 GBP; BTI has 8,551 GBP plus 4 EUR,
3 USD and 1 CAD. A single company-level currency would misclassify those
outliers, which is why the chosen model is per-fact.

## Data model (option B)

- `financial_facts.currency varchar(3)` — per-fact ISO code, backfilled from
  `unit` for plain 3-letter units. `shares`, `pure`, `segment`, crypto/metal
  and indexed units stay NULL. `USD/shares` also stays NULL because the core
  fields do not use per-share facts.
- `fx_currencies(code, name)` — 66 supported fiat codes. Crypto/metals/index
  units (BTC, ETH, XAU, XUA, CLF, UYI, ...) are excluded from conversion.
- `fx_rates(currency, rate_date, usd_per_unit, source)` — USD per one unit of
  `currency`, primary key `(currency, rate_date)`.
- `core_financials` keeps the original columns and adds:
  `currency`, `revenue_usd`, `net_income_usd`, `operating_income_usd`,
  `gross_profit_usd`, `total_assets_usd`, `total_liabilities_usd`,
  `stockholders_equity_usd`, `cash_usd`.

The row `currency` is the currency of the revenue facts (`max(unit)` over the
revenue facts), falling back to the currency of `total_assets`. The USD
columns convert the whole row with that currency. Per-fact currency remains in
`financial_facts` for audits; the row-level choice is the reporting currency
in the normal case (one filing currency per company-year).

## FX source and formula

Primary source: **ECB euro reference rates** (official, no key), daily series
`EXR/D.{CCY}.EUR.SP00.A` from 1999-01-04.

```text
usd_per_eur      = ECB USD/EUR
x_per_eur        = ECB X/EUR
usd_per_unit(X)  = usd_per_eur / x_per_eur
usd_per_unit(EUR)= usd_per_eur
usd_per_unit(USD)= 1 (implicit in the view)
```

Fallback for currencies the ECB does not publish: **Yahoo Finance**
(`<CCY>USD=X`, or `USD<CCY>=X` inverted). Legacy codes are aliased:
`NIS→ILS`, `STD→STN`, `VEF→VES`. The loader stores the actual source per row
(`ecb` / `yfinance`).

Conversion uses the **latest rate on or before `period_end`**, so weekends and
holidays use the previous business day. A missing rate leaves `*_usd` NULL;
it is never replaced with 1.0.

## Loading and refresh

```bash
cd ~/Financial-DataBase
PYTHONPATH=src .venv/bin/python -m scripts.load_fx_rates
PYTHONPATH=src .venv/bin/python -m scripts.detect_reporting_currency --backfill
psql "$DATABASE_URL" -c "REFRESH MATERIALIZED VIEW CONCURRENTLY core_financials"
```

`load_fx_rates` fetches ECB series plus the Yahoo fallback and upserts
`fx_rates`. The backfill updates `financial_facts.currency` in one statement
(~1.9M rows) and is deliberately outside the migration so a long update does
not hold the migration lock. The materialized view is created by migration
0024; it must be refreshed after the FX load because its USD columns are
computed at refresh time.

## Verification

For a converted non-USD filer:

```sql
SELECT cf.fiscal_year, cf.currency, cf.revenue, cf.revenue_usd
FROM core_financials cf
JOIN company_listings cl ON cl.company_id = cf.company_id
WHERE cl.ticker = 'SAN' AND cf.fiscal_year = 2024;
```

Expected: `currency = 'EUR'`, `revenue` in EUR (original), `revenue_usd` =
`revenue × USD_per_EUR` at the latest ECB rate on/before the 2024-12-31
period end.

For a USD filer (AAPL/TTE/AZN/SHEL), `currency = 'USD'` and
`revenue_usd = revenue` exactly.

## Limitations

- **Row-level currency, not per-field.** The row is converted with its revenue
  currency. A rare company-year with material facts in two currencies would
  convert the minority facts with the dominant rate; the per-fact `currency`
  is retained for audits and a future per-field conversion.
- **No rate before 1999.** Facts whose `period_end` predates the ECB series
  (some pre-1999 filings) get NULL `value_usd`.
- **Unsupported units.** UYI (indexed unit) and CLF (Unidad de Fomento) have
  no usable daily pair; their conversions stay NULL.
- **ECB reference rate is a daily 14:15 CET fixing**, not an intraday or
  trade-time rate. Cross rates (GBP→USD via EUR) inherit ECB rounding.
- **Yahoo fallback is not an official source** and can be rate-limited; the
  loader is a one-off batch and stores whatever it obtains.
- **VI 0.33.0 consumes `*_usd`.** `financial_database_repository.py` reads the
  USD columns, keeps the filing `currency` for the `[MIXED-CURRENCY]` badge and
  no longer reads `balance_effective`. VI 0.33 requires FDB 0.3.0+ (older
  schemas lack the USD columns).
- **`companies.currency` is still the default USD.** It is not used by this
  pipeline; the per-fact column is the source of truth.

## Tests

- `tests/unit/test_fx.py` — unit parsing, cross-rate math, zero/missing
  denominators, currency-from-unit mapping.
- `tests/unit/test_migrations.py` — 24 migrations, order and count.
- `tests/integration/test_normalization_migration.py` — `core_financials`
  USD/currency columns, `fx_currencies`/`fx_rates` objects, `financial_facts`
  currency column.
