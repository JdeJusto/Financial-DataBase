# Backlog

## Deferred

- **Ubuntu 26 migration (2026-10-19)**: GitHub Actions `ubuntu-latest`
  migrates to Ubuntu 26. Workflows are pinned to `ubuntu-24.04` (done);
  review and test on `ubuntu-26.04` when available.

## Verified

- **Fresh-clone onboarding audited on 2026-09-30**: the README quick start
  was checked against the real entry points (`python -m financial_database.cli`,
  `financial-db sec sync`, `financial-db prices update --limit`), Compose is
  referenced consistently (`docker compose`), `DATABASE_URL` matches
  `.env.example` and there are no absolute paths. No changes needed. The
  full PostgreSQL setup was not executed in the audit sandbox.
- **Branch protection applied on 2026-09-30**: required checks = Unit tests
  (no database), PostgreSQL integration tests, Compile check (strict, no
  force-push, no deletions).
