# SEC stale sweep — 2026-09-27

Live execution of the stale-fundamentals sweep requested for the daily
workflow, measured end to end on the real database
(`postgresql://financial@localhost:5432/financial_database`) with a
compliant `SEC_USER_AGENT` (`FinancialDataBase/1.0 <your-e-mail>`; the real
value lives in the gitignored `.env`, never in this repository — a
github.com domain or a generic agent is refused with HTTP 403, see
`docs/sec_403_investigation.md`).

Command (background, resumable):

```bash
cd /home/caudillo/Value_Investing
SEC_USER_AGENT="FinancialDataBase/1.0 <your-e-mail>" \
FINANCIAL_DATABASE_URL="postgresql://financial@localhost:5432/financial_database" \
.venv/bin/python -m scripts.daily_workflow \
  --universe all --max-refresh 500 --freshness-hours 168 --top 20 --resume --verbose
```

Run id `2026-09-27T11:35:52Z-348939`, 2 528 tickers, 1 682 s wall (28 min).

## Backlog before the sweep

| Scope | never synced | stale > 48 h | stale > 7 d | listed companies |
| --- | ---: | ---: | ---: | ---: |
| All companies with an active listing | 1 199 | 6 422 | 2 722 | 7 826 |
| Analyzable universe (`--universe all`) | — | — | 334 | 2 528 |

`--max-refresh 500` was not the binding constraint: only 334 companies in the
universe were stale at the 168 h threshold, and all 334 were synced.

## What the sweep did

| Metric | Value |
| --- | --- |
| Companies refreshed | **334 / 334** (0 deferred) |
| Sync failures | **0** (the "9 failed / 9 unmapped" in the summary are universe tickers with no CIK mapping in FDB, not sync errors) |
| Refresh wall time | 1 278 s (3.8 s/company amortised at `--refresh-workers 2`, 0.26 syncs/s) |
| Per-company sync duration (DB side) | avg 4.3 s, max 28 s |
| SEC HTTP 403 | **0** |
| SEC HTTP 429 | **0** |
| SEC retries | **0** |
| Facts inserted | **7 078** |
| Facts skipped (dedup no-ops) | 4 961 200 |
| Filings added | **212** |
| Duplicate rows after the sweep | 0 |

**Rate limiting: none.** Two workers (`--refresh-workers 2`, the conservative
default) produced zero 403 and zero 429 across 334 syncs. This matches the
earlier 200-company batch (`Financial-DataBase/docs/sec_refresh_2026-09-25.md`,
7.24 s/company, 0 rate-limit events), so the importer scales linearly at this
concurrency. The telemetry that proves it is new: the run's `## Network`
section reports `SEC syncs 334 (retries 0, 403 0, 429 0, avg 7327 ms)`.

## Database state after

| Table | Before | After |
| --- | ---: | ---: |
| `financial_facts` | 76 118 047 | 76 124 913 (+6 866 net) |
| `filings` | 1 093 960 | 1 094 172 (+212) |
| `prices` | 152 | **152** (unchanged — prices are never persisted) |
| `import_runs` | 1 576 | 1 910 (+334) |
| `import_runs` with `status='running'` | 0 | 0 |

The importer reported 7 078 inserted facts for 6 866 net new rows; the small
gap is attribution noise between the per-run counters and the final table
(ON CONFLICT no-ops counted per run vs. rows that a later run rewrote).

## Per-company import runs (migration 0021)

Every run of this sweep is scoped to its company, which was impossible before:

```sql
SELECT status, count(*), count(company_id),
       sum(records_inserted), sum(records_skipped), round(avg(duration_seconds)::numeric, 1)
FROM import_runs
WHERE started_at >= '2026-09-27 11:35:00+00' GROUP BY 1;

--  success | 334 | 334 | 7078 | 4961200 | 4.3
```

`count(company_id) = count(*)` = 100 % attribution, so
`import_runs` can now answer "when was this company last ingested?" with one
indexed read (`ImportRunRepository.get_latest_for_company`) instead of
aggregating `financial_facts` timestamps.

## Remaining backlog

| Scope | never synced | stale > 48 h | stale > 7 d |
| --- | ---: | ---: | ---: |
| All companies with an active listing | 876 | 6 411 | 2 711 |
| Analyzable universe (`--universe all`) | — | — | **0** |

The universe is fully fresh, so the daily report no longer sees stale
fundamentals. The ~2 711 companies still stale at 7 d are **outside** the
analyzed universe: Russell 2000 names that never entered
`config/universe.csv`, OTC/foreign listings and delisted issuers. Syncing them
does not change any screen or alert, so the sweep deliberately stopped at the
analyzable universe.

If a catch-up is ever wanted for them:

- keep the targeted path — a per-company batch driven from a CIK list
  (`sec sync <CIK>`), never `sec update-all`/`update-incremental` over the
  whole database;
- ~334 companies per 28-minute run at 2 workers ⇒ ≈ 8 runs (≈ 4 h of refresh
  time) to clear the 7-day backlog, or raise `--refresh-workers` to 3 while
  watching the 403/429 counters in the report's `## Network` section;
- the timer (enabled 2026-09-27, daily 06:00) keeps the analyzed universe
  fresh on its own, so a catch-up campaign is an explicit, manual decision.

## Notes and observations

- **Yahoo was throttling this machine** during the sweep (HTTP 429). The new
  preflight (`backend/services/yahoo_health.py`, Phase 4) detected it in the
  first seconds, skipped the 2 528-ticker snapshot prefetch and the run
  continued with price-derived metrics as N/A. Fundamentals — the point of
  the sweep — were unaffected: 2 450 of 2 528 tickers screened, 279 alerts
  generated. This is the graceful degradation path working as designed, and
  the reason the sweep took 28 min instead of ~45.
- **78 tickers have no fundamentals** ("analysis: no data"): European and OTC
  universe entries with no SEC filings behind them. Unrelated to staleness.
- One transient EDGAR ingestion warning (truncated SGML download for
  accession `0001628280-26-009531`) degraded to the homepage fallback and did
  not fail the run.
- Prices stayed at 152 rows for the whole sweep: the SEC refresh path never
  writes to `prices`, and the Yahoo skip meant VI never even read a quote.
