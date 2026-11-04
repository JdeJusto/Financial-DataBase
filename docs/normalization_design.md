# IFRS normalization + derived balance + quality validator — design (v0.2)

Status: **design only — no migration applied, `financial_facts` untouched.**
Date: 2026-11-04. Target: Financial-DataBase 0.2.0.

## 1. Verified baseline

| Item | Value |
|---|---|
| Repository | `JdeJusto/Financial-DataBase`, `main` = `28beff3` |
| Version | `0.1.0` (`pyproject.toml` and `__version__`) |
| Migrations | 21 (`db/migrations/0001`–`0021`), tracked in `schema_migrations` |
| `financial_facts` | **76,186,195 rows**, **65 GB** total: 21 GB heap + 44 GB indexes |
| Balance-sheet facts | 2,389,534 rows, **562 MB** |
| Mapped facts (VI's 111 concepts) | 17,742,843 rows, **4,485 MB** |
| Core 8-field facts | 5,191,434 rows, **1,192 MB** |
| IFRS facts | 2,092,918 (`namespace='ifrs-full'`) |
| CI | `.github/workflows/ci.yml`: unit tests + PostgreSQL integration tests |
| Tests | 27 test files under `tests/` (`pytest`, `pytest-asyncio`) |

FDB stores the namespace **separately**: examples are
`namespace='ifrs-full', concept='Equity'` / `concept='Liabilities'` /
`concept='ProfitLossFromOperatingActivities'`. A mapping keyed by
`raw_concept='ifrs-full:Equity'` would **not join**; the key must be
`(namespace, concept)`.

### Measured query costs (read-only, production DB)

| Query | Time |
|---|---|
| Join all 76M facts with a 7-row mapping (`VALUES`) | **21.3 s** |
| Same join for one ticker (AAPL FY2025) | **35 ms** |
| Same join for 50 tickers (FY>=2023) | **656 ms** |
| Balance aggregation (Assets/Liab/Equity by company/year/period_end) | **8.0 s** |
| Negative-revenue scan | **4.8 s** |
| Core 8-field scan (5.19M facts) | **21.5 s** (planner chooses a parallel seq scan) |

## 2. Options and decision

### A. `normalized_concept` column on `financial_facts`

- Adding a nullable column is metadata-only in PostgreSQL, but the backfill
  touches **76.2M rows** and adds a text column (~22–55 bytes/row, measured
  at 1.7–4 GB) plus an index.
- It rewrites/bloats a **21 GB heap + 44 GB of indexes**, with WAL and long
  write locks; rollback is another full-table operation.
- **Rejected**: disproportionate write cost on the largest table, for a
  mapping that changes rarely.

### B. `concept_normalization` mapping table

- 111 rows; negligible storage.
- Join measured at **35 ms** for one ticker and **656 ms** for 50 tickers.
- Additive, reversible, and VI's current raw reads are unaffected.
- **Accepted** as the source of truth.

### C. Full materialized view `financial_facts_normalized`

- Would duplicate **~65 GB** (plus index) and refresh scans 76M rows
  (21.3 s just to count the join; writing 65 GB is far heavier).
- **Rejected**.

### C′. Narrow `core_financials` materialized view

- Only the 8 fields VI actually consumes: **5,191,434 rows / 1,192 MB**;
  refresh scan measured at **21.5 s**; add ~one index (~0.5 GB).
- Refreshable daily with `CONCURRENTLY` against a unique index.
- **Accepted** as the read optimization, together with a **non-materialized**
  `financial_facts_normalized` view for ad-hoc/all-concept consumers.

### Decision

**B + C′**:

1. `concept_normalization` (source of truth, 111 rows).
2. `financial_facts_normalized` — a normal **view** (no storage) joining raw
   facts to the mapping, for consumers that need any mapped concept.
3. `core_financials` — a narrow **materialized view** (8 fields, ~1.2 GB)
   refreshed daily.
4. `balance_effective` — a normal **view** over `core_financials` that
   derives `Liabilities_effective = COALESCE(Liabilities, Assets - Equity)`.
5. `data_quality_issues` + `scripts/check_quality.py`.

`financial_facts` is never altered.

## 3. Schema

```sql
-- Source of truth: one row per (namespace, raw concept).
CREATE TABLE concept_normalization (
  namespace text NOT NULL,              -- 'us-gaap' | 'ifrs-full' | ...
  concept text NOT NULL,                -- raw tag, e.g. 'Equity'
  field text NOT NULL,                  -- VI field, e.g. 'stockholders_equity'
  normalized_concept text NOT NULL,     -- canonical US-GAAP name
  combine text NOT NULL DEFAULT 'single'
    CHECK (combine IN ('single', 'sum')),
  notes text,
  PRIMARY KEY (namespace, concept)
);

-- All mapped facts, no storage.
CREATE VIEW financial_facts_normalized AS
SELECT ff.id, ff.company_id, ff.fiscal_year, ff.fiscal_period,
       ff.period_start, ff.period_end,
       cn.field, cn.normalized_concept, cn.combine,
       ff.value, ff.unit
FROM financial_facts ff
JOIN concept_normalization cn
  ON cn.namespace = ff.namespace
 AND cn.concept   = ff.concept;

-- 8-field read layer (5.19M rows / 1.19 GB).
CREATE MATERIALIZED VIEW core_financials AS
SELECT ff.id, ff.company_id, ff.fiscal_year, ff.fiscal_period,
       ff.period_start, ff.period_end,
       cn.field, cn.normalized_concept, cn.combine,
       ff.value, ff.unit
FROM financial_facts ff
JOIN concept_normalization cn
  ON cn.namespace = ff.namespace
 AND cn.concept   = ff.concept
WHERE ff.fiscal_period = 'FY'
  AND cn.field IN (
    'revenue','net_income','operating_income','gross_profit',
    'total_assets','total_liabilities','stockholders_equity',
    'cash_and_equivalents'
  );

CREATE UNIQUE INDEX core_financials_id_idx ON core_financials (id);
CREATE INDEX core_financials_company_year_idx
  ON core_financials (company_id, fiscal_year, period_end);

-- Derived balance, no extra storage.
CREATE VIEW balance_effective AS
SELECT company_id, fiscal_year, period_end,
  max(value) FILTER (WHERE field = 'total_assets')            AS assets,
  max(value) FILTER (WHERE field = 'total_liabilities')       AS liabilities_reported,
  max(value) FILTER (WHERE field = 'stockholders_equity')     AS equity,
  COALESCE(
    max(value) FILTER (WHERE field = 'total_liabilities'),
    max(value) FILTER (WHERE field = 'total_assets')
      - max(value) FILTER (WHERE field = 'stockholders_equity')
  ) AS liabilities_effective,
  (max(value) FILTER (WHERE field = 'total_liabilities') IS NULL
   AND max(value) FILTER (WHERE field = 'total_assets') IS NOT NULL
   AND max(value) FILTER (WHERE field = 'stockholders_equity') IS NOT NULL)
    AS liabilities_derived
FROM core_financials
GROUP BY company_id, fiscal_year, period_end;

-- Quality issues (UUID company ids, matching companies.id).
CREATE TABLE data_quality_issues (
  company_id uuid REFERENCES companies(id),
  fiscal_year smallint,
  field text,
  issue_type text,   -- negative_revenue | unbalanced | absurd_margin | future_date
  severity text,     -- error | warning
  value numeric,
  detected_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, fiscal_year, field, issue_type)
);
```

Revenue components (`RevenueFromSaleOfGoods` + `OtherRevenue`) are seeded
with `combine='sum'`; a total `Revenues` row is `single`. Consumers can sum
the `combine='sum'` rows when no `single` total exists. The same convention
applies to any future split concept.

## 4. Mapping seed

The migration seeds **all 111 concepts** currently present in
`backend/repositories/fdb_concept_mapping.py` (VI), with `field` and a
canonical `normalized_concept`. Core rows:

```sql
INSERT INTO concept_normalization
  (namespace, concept, field, normalized_concept, combine, notes) VALUES
  ('us-gaap','Revenues','revenue','Revenues','single',NULL),
  ('us-gaap','RevenueFromContractWithCustomerExcludingAssessedTax',
   'revenue','Revenues','single',NULL),
  ('us-gaap','NetIncomeLoss','net_income','NetIncomeLoss','single',NULL),
  ('us-gaap','OperatingIncomeLoss','operating_income',
   'OperatingIncomeLoss','single',NULL),
  ('us-gaap','GrossProfit','gross_profit','GrossProfit','single',NULL),
  ('us-gaap','Assets','total_assets','Assets','single',NULL),
  ('us-gaap','Liabilities','total_liabilities','Liabilities','single',NULL),
  ('us-gaap','StockholdersEquity','stockholders_equity',
   'StockholdersEquity','single',NULL),
  ('us-gaap','CashAndCashEquivalentsAtCarryingValue',
   'cash_and_equivalents','CashAndCashEquivalentsAtCarryingValue','single',NULL),
  ('ifrs-full','Equity','stockholders_equity','StockholdersEquity','single',
   'IFRS total equity'),
  ('ifrs-full','Liabilities','total_liabilities','Liabilities','single',NULL),
  ('ifrs-full','Assets','total_assets','Assets','single',NULL),
  ('ifrs-full','ProfitLossFromOperatingActivities','operating_income',
   'OperatingIncomeLoss','single','IFRS operating profit'),
  ('ifrs-full','Revenue','revenue','Revenues','single',NULL),
  ('ifrs-full','RevenueFromSaleOfGoods','revenue','Revenues','sum',
   'sum with OtherRevenue when no total'),
  ('ifrs-full','OtherRevenue','revenue','Revenues','sum',
   'sum with RevenueFromSaleOfGoods when no total'),
  ('ifrs-full','GrossProfit','gross_profit','GrossProfit','single',NULL)
ON CONFLICT (namespace, concept) DO NOTHING;
```

The remaining US-GAAP aliases (CostOfRevenue, SG&A, R&D, debt, cash-flow
tags, etc.) come from the same 111-concept source and use the same field
names; the full `INSERT` is generated in the migration so the mapping stays
the single source of truth.

## 5. Refresh strategy

- **`core_financials`**: daily cron with
  `REFRESH MATERIALIZED VIEW CONCURRENTLY core_financials;` (unique index
  required). Measured scan ~21.5 s; ~1.2 GB. Optional manual refresh at the
  end of an ingest run; if it fails, the previous snapshot stays readable.
- **`financial_facts_normalized`** and **`balance_effective`**: plain views,
  no refresh.
- **`data_quality_issues`**: daily `scripts/check_quality.py` (`TRUNCATE` +
  batch `INSERT`); measured component scans: negative revenue 4.8 s,
  balance aggregation 8.0 s, total job target <60 s.

No triggers: materialized views do not support refresh triggers.

## 6. Backfill plan (v0.2.0, after approval)

1. Create tables/views (DDL above) — seconds.
2. Seed 111 mapping rows — <1 s.
3. `REFRESH MATERIALIZED VIEW core_financials` — **~21.5 s**, ~1.2 GB.
4. Create `core_financials` indexes — ~1–2 min (estimate from 5.19M rows;
   measure during FDB-2).
5. Run `scripts/check_quality.py --full` — target <60 s.
6. Verify `financial_facts` unchanged (row count 76,186,195; size 65 GB;
   same 13 indexes).
7. Measure coverage before/after:
   - Equity missing 127 → ?
   - Operating income 556 → ?
   - Liabilities 343 → ? (derived)
   - Revenue 262 → ?
   - 8/8 fields 724 → ?

No rewrite of `financial_facts`; the backfill only reads it.

## 7. Rollback

```sql
BEGIN;
DROP VIEW IF EXISTS balance_effective;
DROP VIEW IF EXISTS financial_facts_normalized;
DROP MATERIALIZED VIEW IF EXISTS core_financials;
DROP TABLE IF EXISTS data_quality_issues;
DROP TABLE IF EXISTS concept_normalization;
COMMIT;
```

`financial_facts` is untouched, so all existing VI queries keep working.
Pre-migration schema snapshot:
`/tmp/fdb_schema_pre_v0.2.sql` (pg_dump --schema-only), plus the `DROP`
order above.

## 8. Tests

FDB already has 27 test files and CI (unit + PostgreSQL integration). Add
`tests/test_normalization_migration.py`:

1. `test_migration_applies_on_empty_db` — applies cleanly.
2. `test_mapping_table_populated` — 111 rows, PK `(namespace, concept)`.
3. `test_materialized_view_reflects_core_facts` — row count matches the
   5,191,434 core facts.
4. `test_ifrs_equity_normalized` — IFRS tickers get
   `stockholders_equity/StockholdersEquity`.
5. `test_balance_effective_derives_liabilities` — for a company without
   `Liabilities`, `liabilities_effective = assets - equity` within 1 %.
6. `test_rollback_clean` — apply + rollback returns to the pre-migration
   schema.

Plus VI regression after FDB-2: `pytest tests/unit` (2470/2/0),
`pytest tests/api` (125/0), Analysis → Financials smoke, `./vi scorecard
AAPL`.

## 9. Compatibility with VI

VI's repository fetches facts by `company_id`, `fiscal_year`,
`fiscal_period='FY'` and normalizes in Python; it does **not** filter by
`concept` in SQL. Adding a mapping table/MVs is additive and does not break
those queries. VI keeps using `fdb_concept_mapping.py` until VI-1; the FDB
mapping is the future single source of truth.

## 10. Expected impact (to be measured in FDB-2)

- IFRS facts available: 2,092,918; IFRS companies with `Equity` 568,
  `ProfitLossFromOperatingActivities` 409, `Revenue` 403, `GrossProfit` 293
  (all-FDB counts; 81 in the current VI universe).
- `core_financials` covers the 8 fields for 5.19M facts, so VI can stop
  maintaining a duplicate IFRS map and read `balance_effective` directly.
- Coverage deltas will be measured after the backfill; this design does not
  claim them.

## 11. STOP

No migration has been applied. Approval is required before FDB-2
(implementation, backfill, tests, release 0.2.0).

## 12. Implementation note (v0.2.0)

The shipped `core_financials` is the **wide aggregate** — one row per
`(company_id, fiscal_year, period_end)` with the eight canonical metric
columns — not the row-per-fact variant discussed in section 2. It has
**333,027 rows / 48 MB** and refreshes in **19.7 s** concurrently. The
row-per-fact layer is the non-materialized `financial_facts_normalized`
view (18,056,658 mapped facts). The other design decisions (mapping table,
`bank_revenue`, `balance_effective`, quality table) are implemented as
described.

## 13. Known limitations after v0.2.1

### Non-controlling interest aggregation

`core_financials.stockholders_equity` aggregates with `max(value)` per
`(company_id, fiscal_year, period_end)`. When only the tag
`StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`
exists (37 large caps: JNJ, CAT, T, VZ, CSX, ADM, PG, ...), that value
enters as `stockholders_equity`. The value includes non-controlling
interest. This is acceptable for most ratios but differs from strict
"equity attributable to parent".

**Fix scheduled for v0.3.0**: add a `stockholders_equity_parent` column,
separate from the NCI-inclusive value. Consumers choose.

### Non-recoverable tickers at their latest FY (3 of 40)

- **AAMI**: no equity tag in the latest FY. Equity is derivable as
  `assets - liabilities` (84M) but NOT derived: deriving in the inverse
  direction can bring preferred stock, minority interest, or treasury into
  equity incorrectly. Documented as a data gap. FDB still resolves an
  older effective year (FY2023) from previously reported equity.
- **BRUN**: no `total_assets` tag. Assets are derivable as
  `liabilities + equity` but NOT derived (same reason).
- **SKT**: no balance facts in FDB for FY2024/2025. Ingestion gap;
  separate ticket for re-sync.

The v0.2.1 NCI alias recovers 37 of the 40 affected tickers. AAMI, BRUN
and SKT remain documented data gaps rather than being forced with
inverse derivations. The alias also adds equity-only periods to
`core_financials` (**333,027 → 336,196 rows**).
