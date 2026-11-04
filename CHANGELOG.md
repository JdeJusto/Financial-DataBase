# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2026-11-04

### Fixed
- `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`
  (us-gaap and ifrs-full) now maps to `stockholders_equity`. This tag is
  used by 37 large caps (JNJ, CAT, T, VZ, CSX, ADM, PG, ...) that were
  previously returning NULL equity in `core_financials`, causing their
  effective year to be missed in VI's analytical paths.

### Documentation
- Non-controlling interest semantics: `stockholders_equity` includes NCI
  when only the NCI tag exists. Fix scheduled for v0.3.0
  (`stockholders_equity_parent`).
- 3 non-recoverable tickers documented (AAMI, BRUN, SKT): reasons and
  non-derivation rationale. AAMI still resolves an older effective year
  (FY2023) from previously reported equity; BRUN and SKT remain data gaps.

### Coverage
- VI tickers without effective year: **108 → 71** (out of 2,528).
- 37 of the 40 affected tickers recover equity at their latest FY.

### Notes
- No changes to `financial_facts` (76,186,195 rows unchanged).
- `core_financials`: **333,027 → 336,196 rows** (new equity periods);
  refresh measured at **19.8 s** concurrently.

## [0.2.0] - 2026-11-04

### Added
- `concept_normalization` (116 rows): IFRS and US-GAAP raw tags mapped to
  canonical fields, keyed by `(namespace, concept)`. The `*` namespace is a
  concept-only wildcard so one row covers both US-GAAP and IFRS facts with
  the same tag.
- `financial_facts_normalized` view: raw facts joined with their normalized
  field (18,056,658 mapped facts, no storage).
- `core_financials` materialized view: 8 canonical fields (revenue,
  net_income, operating_income, gross_profit, total_assets,
  total_liabilities, stockholders_equity, cash), one row per
  `(company_id, fiscal_year, period_end)`. **333,027 rows / 48 MB**;
  refresh measured at **19.7 s** with `REFRESH MATERIALIZED VIEW
  CONCURRENTLY`.
- `balance_effective` view: `liabilities_effective = COALESCE(
  total_liabilities, total_assets - stockholders_equity)` plus
  `liabilities_derived`.
- `data_quality_issues` table and `scripts/check_quality.py`: negative
  revenue, unbalanced balance, absurd margins, zero revenue and future
  dates. Current scan: 16 negative, 2,674 unbalanced, 16 absurd margins,
  366 zero-revenue warnings, 0 future dates (3,072 rows).
- `bank_revenue` canonical field: bank net-interest / interest-income tags
  are exposed separately and are **not** included in
  `core_financials.revenue` (non-bank comparable revenue). SAN has 57
  `bank_revenue` facts. TD reports a generic `Revenue` tag, so it remains in
  the non-bank bucket until a company-level bank classifier exists (FDB-3).
- Post-ingest refresh: `sec sync-all` calls
  `REFRESH MATERIALIZED VIEW CONCURRENTLY core_financials` once at the end
  of the batch.

### Coverage (VI universe, measured 2026-11-04)
- 8/8 canonical fields: **724 → 857** companies.
- Equity missing: **127 → 128** (one-ticker difference; under review).
- Operating income missing: **556 → 555**.
- Revenue (non-bank) missing: **262 → 243**.
- Liabilities missing: **343 → 22** (derived liabilities included).
- `financial_facts` unchanged: **76,186,195 rows / 65 GB**.

### Notes
- IFRS validation: 18 tickers; equity 18/18 <5 % (all 0.00 %); non-bank
  revenue 14/14 <5 %. SAN/TD differ only by bank revenue definition
  (`docs/ifrs_validation_2026-11-04.md`).
- The design's 5.19M-row `core_financials` was the row-per-fact variant;
  the shipped MV is the wide aggregate (333k rows). The row-per-fact layer
  is `financial_facts_normalized`.
- `financial_facts` is never altered by migration 0022.

### Pending
- **FDB-3**: company-level bank classifier for generic `Revenue` tags (TD,
  others); define the bank-revenue comparator (net interest vs gross).
- **VI-1**: consume `core_financials` / `balance_effective` in
  `financial_data_repository`; VI keeps its own mapping until then.
- Cron refresh deployment.

## [0.1.0] - 2026-09-30

First public release. The package previously declared an unreleased `0.3.0`
in code; with no tags and no consumers, the first public version starts at
`0.1.0` (the unreleased number is not part of the public history).

### Added

- SEC EDGAR ingestion pipeline: company universe (tickers, CIKs, SIC),
  submissions (filings), CompanyFacts (XBRL financial facts), bulk
  ingestion from SEC bulk datasets, and incremental updates with
  checkpoints.
- PostgreSQL schema with 21 ordered migrations (`db/migrations/0001` to
  `0021`), idempotent ingestion with SHA-256 checksums and provenance
  (`import_runs`, raw documents), and `maintenance close-dangling-runs`
  bookkeeping for interrupted runs.
- CLI (`financial-db` / `financial-database`): `migrate`, `status`,
  `sec` (`universe`, `submissions`, `companyfacts`, `sync`, `sync-all`,
  `bulk-ingest`, `update-incremental`, `seed-provider`,
  `seed-exchanges`), `prices update`, `update-all` and `maintenance`.
- Yahoo Finance price ingestion for active listings (split-aware).
- Sector and industry population via Yahoo Finance (resumable).
- Reusable SQL analysis scripts: `scripts/integrity_audit.sql`,
  `scripts/check_ticker_health.sql`, `scripts/verify_history.sql`,
  `scripts/tune_postgres.sql` and `scripts/analysis/` (company overview,
  company comparison, financial series, advanced ratios).
- Documentation: README, `docs/architecture.md`, `docs/database.md`,
  `docs/data-sources.md`, `docs/price_ingestion.md`,
  `docs/analysis_scripts.md` and the operational runbooks.
- Semantic release process: `scripts/release.sh` (with a `first` mode
  used for this initial release), release-consistency tests and the
  tag-verification workflow.

### Known limitations

- OTC companies are excluded from sector population by design.
- Some companies lack XBRL revenue tags (structural, not a bug).
- Integration tests require a live PostgreSQL instance; the release gate
  runs the unit suite, and the integration suite is run manually.
