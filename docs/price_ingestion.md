# Stock Price Ingestion

The financial database includes functionality to ingest stock price data from Stooq, a free financial data provider.

## Overview

Stock price data is essential for financial analysis and is stored in the `prices` table. The ingestion pipeline fetches the latest price data for all active company listings and stores it in the database.

## Data Source: Stooq

[Stooq](https://stooq.com/) provides free CSV data for stocks, indices, forex, etc. without requiring an API key for basic data.

**Advantages of using Stooq:**
- Free access to historical and real-time data
- No API key required for basic usage
- Reliable data for US stocks (primary focus)
- Simple CSV format that's easy to parse

**Limitations:**
- Primarily covers US exchanges (NYSE, NASDAQ, etc.)
- International stocks may have limited coverage
- Data may not be as comprehensive as paid providers

## Architecture

The price ingestion system consists of:

1. **StooqClient** (`src/financial_database/providers/price/client.py`):
   - Handles HTTP requests to Stooq
   - Converts ticker/exchange codes to Stooq symbol format
   - Fetches and parses CSV data

2. **StooqImporter** (`src/financial_database/providers/price/importer.py`):
   - Orchestrates the price update process
   - Gets or creates the Stooq data provider record
   - Retrieves active company listings from the database
   - Fetches latest prices for each listing
   - Inserts new price records (avoiding duplicates via unique constraints)

3. **CLI Commands** (`src/financial_database/cli.py`):
   - `financial-db prices update` - Update stock prices from Stooq
   - `financial-db update-all` - Run both SEC incremental update and stock price update

## Database Schema

Prices are stored in the `prices` table with the following relevant columns:

- `id` - UUID primary key
- `listing_id` - Foreign key to company_listings
- `provider_id` - Foreign key to data_providers (Stooq)
- `price_date` - Date of the price record
- `open` - Opening price
- `high` - Highest price
- `low` - Lowest price
- `close` - Closing price
- `volume` - Trading volume
- `currency` - Currency (defaults to USD for Stooq)
- `source_id` - Unique identifier from the source (format: `stooq:<symbol>`)
- `created_at` - Timestamp when record was created
- `updated_at` - Timestamp when record was last updated

The table has a unique constraint on `(listing_id, price_date, provider_id)` to prevent duplicate price records for the same listing on the same day from the same provider.

## Usage

### Update Stock Prices

```bash
# Update prices for all active listings (uses DATABASE_URL from environment)
financial-db prices update

# Update with custom database URL
financial-db prices update --database-url postgresql://user:pass@host:5432/dbname

# Limit number of listings (for testing)
financial-db prices update --limit 100

# Dry run to validate configuration without writing to database
financial-db prices update --dry-run

# Enable verbose logging
financial-db prices update --verbose
```

### Combined Update

To run both SEC incremental update and stock price update in sequence:

```bash
financial-db update-all

# With custom options
financial-db update-all \
  --sec-max-age-hours 24 \
  --sec-batch-size 100 \
  --price-limit 50 \
  --verbose
```

## Automation

For daily updates, you can set up a cron job:

```bash
# Update prices daily at 4:30 PM EST (after market close)
30 16 * * * /path/to/financial-db prices update >> /var/log/financial-db-prices.log 2>&1

# Or run both SEC and price updates daily
30 16 * * * /path/to/financial-db update-all >> /var/log/financial-db-update-all.log 2>&1
```

## Error Handling

The importer includes robust error handling:

- Network failures are retried by the underlying HTTP client
- Invalid or missing data is logged and skipped
- Duplicate price entries are detected and skipped (not counted as errors)
- Failed listings don't halt the entire process
- Import runs are recorded with status (success/partial/failed) and error details

## Example Usage

After ingesting price data, you can query it with SQL:

```sql
-- Get latest price for Apple (assuming you know the listing ID)
SELECT p.price_date, p.open, p.high, p.low, p.close, p.volume
FROM prices p
JOIN company_listings l ON p.listing_id = l.id
JOIN company_identifiers ci ON l.company_id = ci.company_id
WHERE ci.identifier_value = '0000320193'  -- Apple's CIK
  AND ci.identifier_type = 'CIK'
ORDER BY p.price_date DESC
LIMIT 1;

-- Get price history for the last 30 days
SELECT p.price_date, p.close
FROM prices p
JOIN company_listings l ON p.listing_id = l.id
JOIN company_identifiers ci ON l.company_id = ci.company_id
WHERE ci.identifier_value = '0000320193'
  AND ci.identifier_type = 'CIK'
  AND p.price_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY p.price_date;
```