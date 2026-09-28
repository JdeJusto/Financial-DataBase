# Contributing to Financial-DataBase

Thanks for considering a contribution. This project ingests SEC EDGAR data
(company facts, filings, submissions) into PostgreSQL and exposes reusable SQL
analysis scripts.

## Getting set up

Requires Python 3.13+ and PostgreSQL 14+.

```bash
git clone <your-fork-url>
cd Financial-DataBase
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

`.env` is git-ignored. For the SEC pipeline you need:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection string |
| `SEC_USER_AGENT` | Contact the SEC requires, e.g. `FinancialDataBase/1.0 you@your-domain.com` |
| `SEC_RAW_DIR` / `DATA_RAW_DIR` | where raw filings are cached |

The SEC answers **HTTP 403** to requests without a compliant User-Agent and
to addresses in the `github.com` family; `docs/sec_403_investigation.md` has
the full diagnosis. Use a real e-mail domain you control.

The CLI reads environment variables rather than loading `.env` itself. After
editing the file, load it into the shell before running commands:

```bash
set -a
. ./.env
set +a
```

## Database migrations

Schema changes are plain SQL files in `db/migrations/`, numbered and applied
in order:

```bash
python -m financial_database.cli migrate
```

Do not apply them with `psql -f`: the runner records them in
`schema_migrations`, and a manual application would be re-attempted (and
fail) on the next run. When you add a migration, update the manifest
assertions in `tests/unit/test_migrations.py` (count and expected names).

## Running the tests

```bash
python -m pytest tests/unit -q           # no database required
```

The integration suite requires a separate, migrated PostgreSQL database named
`financial_database_test` by default. Set `DATABASE_URL` for the migration
command and `TEST_DB_*` for the fixtures; never point either at data you care
about. The SQL-analysis integration tests skip unless that database contains
SEC facts for AAPL and MSFT.

## Code style

- PEP 8, type hints on public signatures, docstrings on public APIs.
- Ingestion must stay idempotent: bulk inserts use
  `INSERT ... ON CONFLICT DO NOTHING` and every run records itself in
  `import_runs`.
- Per-company pipelines (`sec sync`, `sec_submissions`, `sec_companyfacts`)
  scope their `import_runs` row to the company; batch pipelines leave
  `company_id` NULL on purpose.
- One concern per commit; messages in the imperative mood.

## Pull requests

1. Fork, branch from `main`.
2. Add tests for new behaviour and, for schema changes, a migration.
3. `python -m pytest tests/unit -q` must be green.
4. Open the PR describing what changed and why.

## Reporting bugs

Open an issue with the bug template: command, expected vs actual, and the
importer's output. Never attach a `.env` or a connection string with a real
password.
