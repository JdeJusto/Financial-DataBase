# Daily price ingestion

`financial-db prices update` imports recent daily OHLCV data from Yahoo Finance using `yfinance` and stores it in the PostgreSQL `prices` table. This command is the active CLI price path; the older Stooq client remains in the source tree but is not used by this command.

## Requirements

Install the price extra, or install the development extra (which includes it):

```bash
pip install -e ".[prices]"
# or, for development and tests:
pip install -e ".[dev]"
```

Set `DATABASE_URL` to the target PostgreSQL database. SEC credentials are not needed for a price-only update.

## Run an update

```bash
# Check the command configuration without making requests or database writes
financial-db prices update --dry-run

# Test with a small number of active listings
financial-db prices update --limit 10

# Update all supported active listings
financial-db prices update
```

The importer reads active listings, maps supported US exchange symbols, requests recent daily history, and selects the latest returned trading date. Duplicate listing/date/provider rows are skipped. Each run is recorded in `import_runs` with its result and counters. `financial-db update-all` also runs a price update after the SEC incremental update.

## Data and limitations

- Yahoo Finance data may be delayed, unavailable, or rate-limited; `yfinance` is an unofficial client and is subject to upstream changes and terms.
- The current symbol mapping covers selected US exchanges; unsupported listings are skipped.
- The importer currently assumes USD and stores the returned close as `adjusted_close`; this is not a separately calculated corporate-action-adjusted close.
- Price history is persisted in this project's database. This differs from Value Investing, which fetches prices on demand and does not persist them.

For scheduled SEC and price updates, see [the daily-update runbook](runbook_daily_update.md). For the database columns and provider lineage, see [the database guide](database.md).
