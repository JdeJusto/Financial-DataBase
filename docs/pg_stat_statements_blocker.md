# pg_stat_statements — what it is, why it is blocked, and what to do instead

Status as of 2026-09-27: **not enabled**. This document records the measured
diagnosis (not an assumption) and the alternatives that work today without a
PostgreSQL restart.

## What it provides

`pg_stat_statements` is a PostgreSQL extension that records every executed
statement in shared memory and exposes aggregated statistics: total
execution time, calls, rows, shared-block hits/reads, per `queryid` and per
statement text (`pg_stat_statements`). It is the standard way to answer
"which query is eating the database?" across a whole workload, and it is how
a slow index or a missing `ANALYZE` gets spotted in production.

The places where this project would benefit: the per-ticker
`financial_facts` read in `backend/repositories/financial_database_repository.py`
(`_list_years_uncached`), the staleness scans in
`backend/services/refresh_service.py`, and the `import_runs` bookkeeping the
SEC importer writes.

## Measured diagnosis

The earlier belief was "blocked because we lack PostgreSQL admin". The
evidence says something narrower:

| Check | Result |
| --- | --- |
| PostgreSQL version | 18.6 |
| `financial` is a superuser? | **yes** (`usesuper = t`) |
| `CREATE EXTENSION pg_stat_statements` | **succeeds** (contrib files installed) |
| `shared_preload_libraries` | empty (source: `default`) |
| `SELECT ... FROM pg_stat_statements` after creating the extension | `ERROR: pg_stat_statements must be loaded via "shared_preload_libraries"` |

So the blocker is **not** privileges and **not** a missing package. It is that
`shared_preload_libraries` is read **only at server start**: the library cannot
be loaded into a running postmaster, so the extension's view exists but can
never answer. Enabling it therefore requires restarting the PostgreSQL service.

That restart was **not** attempted: it interrupts every client of the database
(including the daily workflow's 06:00 timer run) and needs a privileged
systemd/polkit authorization. It is a service action to schedule deliberately,
not a repository change.

The extension created while diagnosing this was dropped again, so the
database is back to its original state (`btree_gist`, `pgcrypto`, `plpgsql`).

## Commands a privileged user would run

```bash
# As superuser (or any role allowed to ALTER SYSTEM):
psql -d financial_database -c "ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';"

# The reload is NOT enough: the library is only picked up at server start.
systemctl restart postgresql          # <- the step that needs a service restart

# Then, in each database that should be observed:
psql -d financial_database -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"

# Useful first queries:
psql -d financial_database -c "
  SELECT calls,
         round(total_exec_time::numeric, 1)  AS total_ms,
         round(mean_exec_time::numeric, 2)   AS mean_ms,
         rows,
         left(query, 80) AS query
  FROM pg_stat_statements
  WHERE query ILIKE '%financial_facts%'
  ORDER BY total_exec_time DESC
  LIMIT 20;"

psql -d financial_database -c "SELECT pg_stat_statements_reset();"
```

To undo:

```bash
psql -d financial_database -c "ALTER SYSTEM RESET shared_preload_libraries;"
systemctl restart postgresql
```

## Alternatives that work without a restart

These are what this project uses today.

1. **`log_min_duration_statement` at role level — no restart, no superuser.**
   Verified working on this machine (then reset to leave no trace):

   ```sql
   ALTER ROLE financial SET log_min_duration_statement = 1000;  -- log queries > 1s
   ```

   Every new session from that role then logs its slow statements to the
   PostgreSQL log with duration and query text, which is enough to find the
   offender during a window where it matters (a daily run, a catch-up batch).
   Revert with `ALTER ROLE financial RESET log_min_duration_statement;`.
   It is a per-role setting, so it can be turned on for a diagnostic window
   and removed afterwards without touching `postgresql.conf`.

2. **`EXPLAIN (ANALYZE, BUFFERS)` on the specific query.** No configuration
   at all, and it shows the plan, the actual row counts and the buffer
   activity. This is how the per-ticker facts read was tuned
   (`ORDER BY`/`LIMIT` pushdown, the calendar-year ranking for the fiscal-year
   end). It measures one statement at a time, which is exactly the scope of a
   code change.

3. **Python-side timing with `cProfile`.** Measures the whole call path
   including result materialization, which SQL-level tools miss: the
   `RealDictRow` construction cost (29 % of the analysis time) is invisible to
   `pg_stat_statements` and obvious in a profile. Every optimization in this
   project's recent history (the facts read, the fundamentals cache, the
   year-set cache) was found this way.

4. **Cache-hit rates and run-state counters** (`backend/services/run_state.py`,
   `analysis_cache` stats, the `## Network` section of the daily report) tell
   how often the database is consulted at all, which is the cheapest way to
   keep load down while the query-level tooling is unavailable.

## Recommendation

Enable `pg_stat_statements` at the next convenient maintenance window (it is a
one-line change plus one restart, and it needs no new package on this host),
but do not block any work on it: use (1) for a diagnostic window and (2)/(3)
for everything else. The performance work so far has not needed it.
