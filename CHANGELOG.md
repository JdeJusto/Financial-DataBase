# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
