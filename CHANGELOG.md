# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-09-30

Baseline entry: the version the package already declared when the semantic
release process (`scripts/release.sh`) was introduced. From here on every
release gets its own dated entry, created by the script.

### Added

- SEC EDGAR ingestion (`sec sync`): company facts, filings, company
  identifiers and XBRL concepts into the `companies`, `financial_facts`,
  `filings` and `company_identifiers` tables.
- Yahoo Finance price ingestion (`prices`, split-aware) behind the price
  provider extra.
- Sector and industry enrichment with resumable population.
- Reusable SQL analysis scripts under `scripts/analysis/`.
- `financial-db` / `financial-database` CLI entry points.
- Schema migrations under `src/financial_database/db/migrations/`.
