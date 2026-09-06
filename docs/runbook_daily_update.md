# Daily Update Runbook

This document describes the procedures for performing daily updates of the financial database, including both SEC filings and stock price data.

## Overview

The financial database requires regular updates to maintain data accuracy and relevance. This runbook outlines two approaches:
1. Separate commands for SEC and price updates
2. Combined update-all command

## Prerequisites

- PostgreSQL database running and accessible
- Environment variables set:
  - `DATABASE_URL` (optional, defaults to local development)
  - `SEC_USER_AGENT` (required for SEC operations)
- Virtual environment activated (`.venv/bin/activate`)

## Option 1: Separate Updates

### SEC Incremental Update

Updates SEC data (filings, financial facts) for companies that have stale data.

```bash
python src/financial_database/cli.py sec update-incremental \
    --max-age-hours 24 \
    --batch-size 100
```

**Parameters:**
- `--max-age-hours`: Maximum age of data before considering it stale (default: 24)
- `--batch-size`: Number of companies to process in each batch (default: 100)
- `--limit`: Limit number of companies to process (for testing)
- `--dry-run`: Validate without writing to database
- `--verbose`: Increase logging detail

### Stock Price Update

Updates stock prices from Yahoo Finance for all active listings.

```bash
python src/financial_database/cli.py prices update \
    --limit 1000
```

**Parameters:**
- `--limit`: Limit number of listings to process (for testing)
- `--dry-run`: Validate without writing to database
- `--verbose`: Increase logging detail

## Option 2: Combined Update

The `update-all` command runs both SEC incremental update and stock price update sequentially.

```bash
python src/financial_database/cli.py update-all \
    --sec-max-age-hours 24 \
    --sec-batch-size 100 \
    --price-limit 1000
```

**Parameters:**
- `--sec-max-age-hours`: Maximum age of SEC data before considering it stale (default: 24)
- `--sec-batch-size`: Number of companies to process in each SEC batch (default: 100)
- `--sec-limit`: Limit number of companies to process for SEC update (for testing)
- `--price-limit`: Limit number of listings to process for price update (for testing)
- `--dry-run`: Validate without writing to database
- `--verbose`: Increase logging detail

## Scheduling

To automate daily updates, you can use cron jobs or similar scheduling mechanisms.

### Example Cron Entries

```cron
# Run SEC update daily at 2 AM
0 2 * * * source /home/caudillo/Financial-DataBase/.venv/bin/activate && python /home/caudillo/Financial-DataBase/src/financial_database/cli.py sec update-incremental >> /var/log/financial-db-sec-update.log 2>&1

# Run price update daily at 3 AM
0 3 * * * source /home/caudillo/Financial-DataBase/.venv/bin/activate && python /home/caudillo/Financial-DataBase/src/financial_database/cli.py prices update >> /var/log/financial-db-price-update.log 2>&1

# Or run combined update daily at 2:30 AM
30 2 * * * source /home/caudillo/Financial-DataBase/.venv/bin/activate && python /home/caudillo/Financial-DataBase/src/financial_database/cli.py update-all >> /var/log/financial-db-update-all.log 2>&1
```

## Monitoring

### Checking Update Status

To check when data was last updated:

```sql
-- Check last SEC sync time
SELECT legal_name, last_synced_at
FROM companies
WHERE last_synced_at IS NOT NULL
ORDER BY last_synced_at DESC
LIMIT 10;

-- Check latest price dates
SELECT cl.ticker, MAX(p.price_date) as last_price_date
FROM company_listings cl
JOIN prices p ON cl.id = p.listing_id
GROUP BY cl.ticker
ORDER BY last_price_date DESC
LIMIT 10;
```

### Checking Import Runs

```sql
-- Check recent SEC import runs
SELECT ir.status, ir.records_inserted, ir.finished_at
FROM import_runs ir
JOIN data_providers dp ON ir.provider_id = dp.id
WHERE dp.name = 'SEC EDGAR'
ORDER BY ir.finished_at DESC
LIMIT 5;

-- Check recent price import runs
SELECT ir.status, ir.records_inserted, ir.finished_at
FROM import_runs ir
JOIN data_providers dp ON ir.provider_id = dp.id
WHERE dp.name = 'Yahoo Finance'
ORDER BY ir.finished_at DESC
LIMIT 5;
```

## Troubleshooting

### Common Issues

1. **SEC_USER_AGENT not set**
   - Error: "SEC_USER_AGENT environment variable is required"
   - Solution: Set `export SEC_USER_AGENT="your-email@example.com"`

2. **Rate limiting from Yahoo Finance**
   - Symptom: Empty price data or errors
   - Solution: The yfinance client includes built-in rate limiting. For extreme cases, add delays between requests.

3. **Database connection issues**
   - Error: "could not connect to server"
   - Solution: Verify PostgreSQL is running and `DATABASE_URL` is correct

4. **Missing data for specific companies**
   - Check if the company has an active listing
   - Verify the exchange code mapping works with Yahoo Finance

### Log Files

All operations log to stdout/stderr. For persistent logging, redirect output to files when running via cron or manually.

## Data Validation

After running updates, consider running these validation checks:

```sql
-- Check for companies with no recent SEC data
SELECT c.legal_name, c.last_synced_at
FROM companies c
WHERE c.last_synced_at < NOW() - INTERVAL '2 days'
ORDER BY c.last_synced_at ASC;

-- Check for listings with no price data
SELECT cl.ticker, cl.id
FROM company_listings cl
LEFT JOIN prices p ON cl.id = p.listing_id
WHERE p.id IS NULL
  AND cl.is_active = true
LIMIT 10;
```

## Maintenance

- Monitor database storage growth (prices table can grow large)
- Consider archiving old price data if needed
- Regularly check for failed import runs and investigate causes
- Keep the yfinance library updated for best compatibility

## Security Notes

- The SEC_USER_AGENT should be a valid email address or identifier
- Database credentials should be managed securely (consider using .pgpass file)
- Avoid running updates during peak business hours if concerned about network impact

---

Last updated: $(date)