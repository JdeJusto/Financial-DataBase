# SEC refresh run — 2026-09-27 (bounded batch, 200 companies)

Live refresh of a bounded batch through the Value Investing daily workflow
(`--universe sp500 --freshness-hours 48 --max-refresh 200 --resume`) with a
compliant User-Agent (`FinancialDataBase/1.0 jaimedejusto@gmail.com`, kept in
the git-ignored `.env`). Purpose: measure the bulk importer at batch scale
after the 2026-09-24 changes (bulk `INSERT ... ON CONFLICT`, memoized
`get_company_tickers`, `--limit` fix, `last_synced_at` stamping).

## 1. Access check

```
$ curl -I -H "User-Agent: FinancialDataBase/1.0 jaimedejusto@gmail.com" \
    https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json
HTTP=200
```

The github.com address family is blocked by SEC (HTTP 403, deterministic —
see `docs/sec_403_investigation.md`); a normal email domain works. No proxy is
configured and there is no SEC outage.

## 2. Staleness before the run

Per-company freshness = `GREATEST(max(financial_facts.updated_at),
max(filings.created_at), companies.updated_at)` (the same expression the
refresh service uses):

| Scope | never synced | >168 h (7 d) | >72 h | >48 h | >24 h | median age |
|---|---|---|---|---|---|---|
| US tickers with a CIK (7,840) | — | 2,817 | — | — | 7,840 | 74 h |
| `--universe sp500` (500) | 0 | **0** | 374 | 499 | 499 | — |

The S&P 500 had **nothing** to refresh at the default 168 h threshold (the
2026-09-24 audit already covered it); a first run of the day refreshed the
single stale company (1 refreshed, 499 fresh, 221 s total). To actually
measure the importer at batch scale the threshold was set explicitly to
**48 h**, which marks 499 sp500 companies stale and lets `--max-refresh 200`
select the 200 closest to current (299 deferred to the next run).

## 3. The batch (48 h threshold, cap 200)

| Metric | Value |
|---|---|
| Wall clock (launch → report) | 32 m 51 s (10:09:51Z → 10:42:42Z) |
| Refresh phase (workflow timing) | **1,448 s** for 200 companies → **7.24 s/company** (2 workers) |
| Throughput | 8.3 companies/min; 200/200 succeeded |
| Facts inserted (new) | **562** |
| Facts skipped (already present) | **4,920,981** |
| Filings inserted | 16 |
| Companies stamped `last_synced_at` | 200 (201 including the first run) |
| Failures | **0** |
| Rate-limit events (403/429) | **0** |
| Average facts per company | ~24,600 (mega-caps: AAPL, JPM, WFC, CVX…) |
| Deferred by `--max-refresh` | 299 |
| `prices` table | **152 rows, untouched** |
| Duplicates after the run | **0** (201-company check and full 76.1 M-row scan) |

Full workflow timings: `refresh 1448 s · prices 99 s · analysis 209 s ·
alerts 0 s · total 1657 s`; 499/500 tickers passed the screen (HONA has no
fundamentals — a known mapping gap, not a refresh failure).

## 4. Performance vs the offline estimates

The offline benchmark (test DB, one transaction, mocked client) measured the
facts-insert layer at **1.85 ms/fact before → 0.25 ms/fact after (7.3×)**. At
the ~24,600 facts/company of this batch:

| | DB insert per company | 200 companies with 2 workers |
|---|---|---|
| Old per-fact path (1.85 ms/fact, measured) | ~45.5 s | ~76 min (inserts only) |
| New bulk path (0.25 ms/fact, measured) | ~6.2 s | ~10 min (inserts only) |
| **Observed end-to-end** | — | **24.1 min** (download + parse + submissions + inserts) |

So the facts insert is no longer the bottleneck: roughly 6 s per company of
the 7.24 s observed, the rest being SEC downloads, JSON parsing and the
submissions/universe upserts. Idempotency held: 4.92 M existing facts were
skipped, 562 new ones inserted, and the unique-key scan found **zero**
duplicates afterwards (2 m 33 s for the full 76.1 M-row check).

## 5. Issues found and fixed during the batch

- **Progress was invisible during a long refresh.** With `refresh_workers > 1`
  the `progress_cb` hook only fired when the whole batch returned, so the run
  state showed `refresh 0/200` after six minutes even though companies were
  already syncing (`_sync_many` now fires it from `as_completed`;
  verified live: `refresh 2/3` 16 s into a 3-company batch).
- **Refresh status line printed ticker lists instead of counts**
  (`staleness_ranked` returns lists; the line interpolated them directly).
  Fixed with `len()`; a real run now reads
  `200 refreshed · 499 stale · 1 fresh · 299 deferred (--max-refresh)`.

## 6. Recommendations for the full-universe run

1. **Keep the compliance rules**: a descriptive UA with a normal email domain
   (never github.com), 2 refresh workers, and the SEC client's own pacing —
   200 companies produced **0** rate-limit events.
2. **Keep the default 168 h threshold** for daily operation; 7,840 US CIK
   companies are currently >7 d stale, so a 2,817-company backlog remains.
   `--max-refresh 200` per run is ~24 min of refresh, so a full sweep at that
   cadence takes ~14 daily runs (or raise `--max-refresh` while keeping
   `--refresh-workers 2`, and watch for 403/429 in the log).
3. **Never use `update-all`**: the targeted per-CIK refresh is what makes this
   measurable and interruptible (it is also what the new run checkpoint
   resumes).
4. **Watch the new checkpoint** (`data/reports/daily_run_state.json`) during
   long runs: completed companies are never synced twice, and a
   SIGTERM/power loss resumes from the last company.
5. After the sweep, re-run `check-ticker-health`-style queries for the ~2,817
   still-stale companies; foreign/OTC filers with sparse data are expected to
   remain and are harmless for the analysis universe.
