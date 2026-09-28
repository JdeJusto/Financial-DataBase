# Pull request

<!-- One-line summary of the change. -->

## What changed

<!--
What the PR does, and why. If it changes the schema, the ingestion
semantics, or the recorded provenance, say so explicitly.
-->

## Checklist

- [ ] `python -m pytest tests/unit -q` is green
- [ ] Tests added or updated for the new behaviour
- [ ] **No secrets**: no `.env`, database credentials, API keys, or private
      third-party contact data. The maintainer contact is intentionally listed
      in `SECURITY.md` and `CODE_OF_CONDUCT.md`.
- [ ] No personal absolute paths (`/home/<user>/…`) in code, docs or unit files
- [ ] Docs updated (`docs/`, README) where behaviour or setup changed
- [ ] Commit messages in the imperative mood, one concern per commit

## Project invariants

- [ ] Schema changes ship as a **numbered migration** in `db/migrations/` and
      the manifest assertions in `tests/unit/test_migrations.py` are updated
      (count + expected names)
- [ ] Migrations are applied with `python -m financial_database.cli migrate`,
      never with a bare `psql -f` (the runner records them in
      `schema_migrations`)
- [ ] Ingestion stays idempotent: bulk inserts use `ON CONFLICT DO NOTHING`
      and every run records itself in `import_runs`
- [ ] Per-company pipelines scope `import_runs.company_id`; batch pipelines
      leave it NULL on purpose
- [ ] SEC requests keep a compliant `SEC_USER_AGENT` and stay bounded — no
      database-wide sweep unless explicitly requested
- [ ] All SQL is parameterised; no string interpolation of user input

## Verification

<!--
The command and its output. For ingestion changes, the row counts
(records_inserted / records_skipped) and a duplicate check:

    SELECT count(*) FROM (
      SELECT 1 FROM financial_facts
      GROUP BY company_id, concept, period_start, period_end, filing_id, source_id
      HAVING count(*) > 1
    ) d;   -- expect 0
-->

```
```

## Additional context

<!-- Anything a reviewer should know before approving. -->
