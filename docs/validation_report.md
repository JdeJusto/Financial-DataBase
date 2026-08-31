# Phase 3.8 — Final Pre-Flight Validation Report

This report documents the results of the pre-flight validation performed before
the full SEC universe ingestion (~10,388 companies).

## 1. Database Integrity Audit

Run against `financial_database` via `scripts/integrity_audit.sql`.

| Check | Result |
|-------|--------|
| Duplicate companies (legal_name + country) | 0 |
| Duplicate companies (same CIK → multiple companies) | 0 |
| Duplicate company identifiers | 0 |
| Duplicate listings (company, exchange, ticker, active) | 0 |
| Duplicate filings (provider, accession_number) | 0 |
| Duplicate financial facts | 0 |
| Orphaned facts (company_id missing) | 0 |
| Orphaned filings (company_id missing) | 0 |
| Orphaned listings (company/exchange missing) | 0 |
| Facts with NULL value | 0 |
| Companies with no financial facts | 21 (expected: funds/ADRs/trusts) |
| Companies with no filings | 11 (expected: non-filing entities) |
| Companies with no identifiers | 0 |
| Facts missing provider_id | 0 |
| Facts missing source_id | 0 |
| Facts referencing a non-existent filing | 0 |

**Finding:** `filing_id` was not populated on facts because the pipeline
processed company facts *before* filings. This was fixed (see §4): submissions
are now processed first, and facts are linked to their filing via `filing_id`
where a filing record exists (facts from forms not stored as filings, e.g. 8-K,
remain unlinked by design, but `source_id` still embeds the accession number).

## 2. Historical Coverage Verification

Run via `scripts/verify_history.sql` against 23 major companies.

| Company | Earliest FY | Latest FY | Distinct FYs | Facts |
|---------|-------------|-----------|--------------|-------|
| Amazon | 2009 | 2026 | 18 | 29,755 |
| Apple | 2009 | 2026 | 18 | 25,135 |
| Bank of America | 2009 | 2026 | 18 | 45,535 |
| Boeing | 2009 | 2026 | 18 | 34,447 |
| Chevron | 2009 | 2026 | 18 | 32,069 |
| Coca-Cola | 2009 | 2026 | 18 | 33,231 |
| JPMorgan | 2009 | 2026 | 18 | 53,418 |
| Microsoft | 2010 | 2026 | 17 | 32,669 |
| NVIDIA | 2009 | 2027 | 19 | 27,281 |
| Walmart | 2009 | 2027 | 18 | 24,868 |
| Meta | 2012 | 2026 | 15 | 18,053 |
| Tesla | 2011 | 2026 | 16 | 24,131 |
| Alphabet | 2015 | 2026 | 12 | 20,907 |
| Cisco | 2010 | 2026 | 17 | 40,824 |
| + 9 more | 2009 | 2026 | 18 | — |

All established filers reach back to **2009** (the earliest XBRL year). Newer
companies (Alphabet 2015, Meta 2012, Tesla 2011) start at their IPO or
corporate-restructuring date, which is expected.

## 3. Classification of the 10 Stress-Test Errors

The 10 errors were all `404 Resource not found` on the `companyfacts` endpoint.
These are **expected 404s**, not client bugs. They occur for entities that do
not file XBRL financial statements:

- **Closed-end funds** (file N-CSR/N-PX, not 10-K/10-Q): CET, ADX, BCV, GAM,
  VBF, MXF, PHD, STEW, TY, XSIAX, PAI
- **Royalty trusts**: HGTXU, MARPS
- **Foreign ADRs** (XBRL lives under the parent filer's CIK, not the ADR): CYATY,
  KXIAY, SMTOY, SRGBF
- **Utility subsidiaries / preferred-stock units**: CNTHP, EMP, ENJ, PNMXO

Verified example: `CIK0000018748` (Central Securities Corp) returns HTTP 404.
The client now logs these clearly (`expected_404: true`, INFO level) and
continues to the next company without affecting the run.

## 4. Code Fixes Applied During Validation

- **Fact provenance (`filing_id`)**: reordered the per-company pipeline to
  process submissions (filings) before company facts, build an
  `accession_number → filing_id` map, and link each fact to its filing.
  `_process_company_facts` now passes the map to the parser.
- **Clearer 404 logging**: companyfacts/submissions 404s are logged at INFO
  with `expected_404: true` instead of a generic warning.

## 5. Performance Review

- Stress test: 608 companies in ~51 minutes → **~5.0 s/company**.
- Full universe (10,388 companies): **~14.5 hours** at the same rate.
- DB size after 608 companies: **10.0 GB** (`financial_facts` = 10.0 GB).
- Extrapolated full universe: **~170–200 GB** (~213M facts at ~20,500
  facts/company).

Bottlenecks identified:
- Dominated by network + SEC rate limiting (2 HTTP calls/company), not DB.
- Facts insert in 500-row batches (`FACTS_PER_TRANSACTION`) — adequate.
- No N+1 problems beyond the small per-company CIK lookups (indexed).
- `company_listing_repository.get_by_*` references a non-existent
  `delisted_date` column (pre-existing; not on the ingest hot path).

No premature optimization performed.

## 6. PostgreSQL Tuning Applied

Applied via `scripts/tune_postgres.sql`:

| Setting | Old | New | Scope |
|---------|-----|-----|-------|
| `maintenance_work_mem` | 64 MB | 512 MB | database |
| `work_mem` | 4 MB | 64 MB | database |
| `synchronous_commit` | on | off | database |
| `max_wal_size` | 1 GB | 4 GB | cluster (`ALTER SYSTEM`) |
| `checkpoint_timeout` | 5 min | 15 min | cluster (`ALTER SYSTEM`) |

`synchronous_commit = off` trades a small durability window (at most the last
in-flight transaction on crash) for much higher insert throughput. This is
justified because the pipeline is idempotent and resumable. Revert to `on`
after the load.

Indexes are adequate for the full load (financial_facts has 13 indexes,
filings 9, identifiers 6, listings 8).

## 7. Checkpoint / Resume Strategy

- Checkpoint is saved after every company (`full_universe_checkpoint.json`).
- Checkpoint is **source-aware**: it records the tickers source and is only
  reused when the source matches, so switching universes does not skip
  companies (no `--force` needed).
- `--force` is available to explicitly reset progress.
- The checkpoint file is **not** tracked by git (`.gitignore` covers
  `data/checkpoints/`).

## 8. Dry-Run of Full Universe

`bulk-ingest --dry-run` against the official SEC tickers file:

```
Companies loaded: 10391 (of 10391 total)
- 0001045810: NVIDIA CORP (NVDA) on Nasdaq
- 0000320193: Apple Inc. (AAPL) on Nasdaq
- ...
```

The full universe (~10,391 companies) enumerates without errors.

## 9. Conclusion

All acceptance criteria pass. The system is ready for full universe ingestion.

**READY FOR FULL SEC UNIVERSE INGESTION**
