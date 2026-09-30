# Financial-DataBase

[English](README.md) · [Español](README.es.md)

A Python and PostgreSQL project for ingesting public-company filings and financial facts, preserving their source history, and making the data available through a CLI and reusable SQL analyses.

> **Design principle:** “Fools admire complexity; geniuses admire simplicity.” Keep the schema, data flow, and operational commands understandable; record provenance rather than hiding it behind extra layers.

## What it does

- Imports company identifiers, SEC filings, submissions, and XBRL company facts.
- Stores normalized facts and daily market prices in PostgreSQL with provider provenance.
- Records import runs, supports resumable bulk ingestion, and provides reusable SQL analyses.
- Exposes the `financial-db` command-line tool.

## Data sources and external tools

| Source or tool | How it is used |
| --- | --- |
| [SEC EDGAR](https://www.sec.gov/edgar) | Primary source for company identifiers, filings, submissions, and XBRL Company Facts. SEC requests require a descriptive `SEC_USER_AGENT` with valid contact details and must follow SEC access policies. |
| [Yahoo Finance](https://finance.yahoo.com/) via [`yfinance`](https://github.com/ranaroussi/yfinance) | Current source used by `financial-db prices update` for daily OHLCV data. Unlike Value Investing's on-demand price service, this project **stores imported prices** in its PostgreSQL `prices` table. Coverage, delays, and availability depend on Yahoo. |
| Stooq | An older provider implementation remains in the source tree; the current `prices update` command uses Yahoo Finance, not Stooq. |
| PostgreSQL | Required database for normalized records, migrations, provenance, and imported prices. A local development service is available through Docker Compose. |

The tracked `data/company_tickers_full.json` is an SEC company/ticker reference snapshot for reproducible identifier mapping. It is public reference data, not a substitute for current SEC filings. This project's MIT license covers the code only; third-party data and trademarks remain subject to their providers' terms.

The core stack is Python, PostgreSQL, Psycopg 3, `aiohttp`, and `ijson`;
Yahoo price ingestion additionally uses `yfinance` and pandas. The full
dependency list and optional extras are declared in `pyproject.toml`.

## Quick start

Requirements: Python 3.13+ and PostgreSQL 14+ (the provided Compose file uses PostgreSQL 18). The `dev` extra includes the Yahoo price dependencies.

```bash
git clone https://github.com/JdeJusto/Financial-DataBase.git
cd Financial-DataBase
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env
```

Edit `.env`: set `DATABASE_URL` and replace the example `SEC_USER_AGENT` with a descriptive application name and a real contact address. The CLI reads environment variables; load the file into your shell before running commands:

```bash
set -a
. ./.env
set +a

docker compose up -d postgres
python -m financial_database.cli migrate
financial-db sec sync 0000320193
financial-db prices update --limit 10
```

The final command makes live requests to Yahoo Finance and writes imported prices to the database. The default Compose credentials are for local development only; do not reuse them in a deployed environment.

For a cautious SEC bulk-ingestion run, begin with `financial-db sec bulk-ingest --dry-run` and a limited run. A full historical load can require substantial storage and many SEC requests; see the [full-load runbook](docs/runbook_full_load.md).

## Tests

```bash
python -m pytest tests/unit -q           # no database required
```

Repository and SQL integration tests need a separate PostgreSQL test database.
With the Compose database running, create and migrate it once:

```bash
docker compose up -d postgres
docker compose exec postgres createdb -U financial financial_database_test
DATABASE_URL=postgresql://financial:test@localhost:5432/financial_database_test \
  python -m financial_database.cli migrate
```

Then point the test fixtures at that database and run the integration suite:

```bash
TEST_DB_NAME=financial_database_test \
TEST_DB_USER=financial TEST_DB_PASSWORD=test \
TEST_DB_HOST=localhost TEST_DB_PORT=5432 \
python -m pytest tests/integration -q
```

The SQL-analysis integration tests skip unless the test database contains SEC
facts for AAPL and MSFT. Never point test fixtures at a database with data you
care about.

## Project layout

```text
src/financial_database/  CLI, SEC and price providers, database repositories
db/migrations/          ordered PostgreSQL schema migrations
scripts/analysis/       reusable SQL queries
scripts/stress/         stress-test utilities
scripts/dev/            development and maintenance helpers
tests/unit/             isolated tests
tests/integration/      database and ingestion tests
docs/                   guides, runbooks, and historical reports
```

## Documentation

- [Architecture](docs/architecture.md) · [Database schema](docs/database.md)
- [Data sources](docs/data-sources.md) · [Price ingestion](docs/price_ingestion.md)
- [SQL analysis scripts](docs/analysis_scripts.md)
- [Daily updates](docs/runbook_daily_update.md) · [Full SEC load](docs/runbook_full_load.md)
- [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Code of Conduct](CODE_OF_CONDUCT.md)

## Releasing

Releases follow [Semantic Versioning](https://semver.org/). See [CONTRIBUTING.md](CONTRIBUTING.md#releasing) for the process.

## License

[MIT](LICENSE). The license applies to the project's code, not to external data or provider terms.
