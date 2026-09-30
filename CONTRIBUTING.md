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

## Releasing

Use `./scripts/release.sh <patch|minor|major> "<message>"` from a clean `main`
branch with the tests passing. For the very first release use
`./scripts/release.sh first "<message>"`: it tags the version already declared
in `src/financial_database/__init__.py` (no bump) and reuses the existing
`CHANGELOG.md` entry as the release notes.

The script:

1. Bumps the version in `src/financial_database/__init__.py` and
   `pyproject.toml` (they must stay in sync; a consistency test enforces it).
2. Updates `CHANGELOG.md` (Keep a Changelog).
3. Commits, creates the annotated tag `vX.Y.Z` and pushes.
4. Creates the GitHub release (`gh release create`).

It refuses to continue if the working tree is dirty, `main` is not in sync with
`origin/main`, the unit tests fail or the `ruff` debt grows beyond
`config/lint_baseline`. The integration suite needs PostgreSQL and is out of the
release gate (CI runs it on every push). Use `--dry-run` to prepare the changes
without committing, tagging or pushing.

Versioning rules:

- **patch** (`0.3.X`): bug fixes, docs, small polish.
- **minor** (`0.X.0`): new features, new providers, new concepts, non-breaking.
- **major** (`X.0.0`): breaking changes — e.g. schema migrations that break
  compatibility or CLI renames. The script warns when new migrations land on a
  `patch` release.

The package version must match the top `CHANGELOG.md` entry and the
`pyproject.toml` version; `tests/unit/test_release_consistency.py` enforces it
in the regular suite.

## Reporting bugs

Open an issue with the bug template: command, expected vs actual, and the
importer's output. Never attach a `.env` or a connection string with a real
password.
