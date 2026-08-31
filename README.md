# Financial Database

## Features

- Normalized schema for financial data
- Support for multiple data providers
- Full provenance tracking with source identifiers
- Audit trails for all import operations
- Flexible design to accommodate various financial data types
- Constraint-based data integrity
- Indexed for common query patterns
- **SEC EDGAR ingestion pipeline** - Production-quality SEC data import

## Schema Overview

The database consists of the following core tables:

- `companies` - Basic company information
- `company_identifiers` - Various company identifiers (CIK, FIGI, etc.)
- `company_listings` - Exchange listings for companies
- `exchanges` - Stock exchanges
- `data_providers` - Sources of financial data
- `filings` - SEC filings and similar regulatory documents
- `financial_facts` - Normalized financial statement data
- `prices` - Historical price and volume data
- `dividends` - Dividend declarations and payments
- `splits` - Stock split events
- `raw_documents` - Metadata for preserved raw data files
- `import_runs` - Audit trail for data import operations

## Getting Started

### Prerequisites

- PostgreSQL 12+
- Python 3.8+ (for running tests and migrations)

### Installation

1. Clone the repository
2. Copy `.env.example` to `.env` and configure your database connection
3. Run the database migrations:
   ```bash
   ./scripts/migrate.sh
   ```
4. Run the test suite to verify everything is working:
   ```bash
   python -m pytest tests/
   ```

### SEC EDGAR Setup

To use the SEC ingestion pipeline, you must configure a User-Agent as required by SEC:

1. Edit `.env` and set `SEC_USER_AGENT`:
   ```
   SEC_USER_AGENT=your-app/1.0 contact@yourdomain.com
   ```
   The SEC requires a unique, descriptive User-Agent with contact information.

2. Configure raw data storage (optional):
   ```
   DATA_RAW_DIR=./data/raw
   ```
   Raw SEC responses are stored here for provenance and re-processing.

## SEC EDGAR Ingestion

The `financial-db` CLI provides SEC ingestion commands:

```bash
# Seed SEC provider and exchanges
financial-db sec seed-provider
financial-db sec seed-exchanges

# Import SEC company universe (tickers, CIKs, exchanges)
financial-db sec universe

# Import filings for a specific company (by CIK)
financial-db sec submissions 0000320193

# Import XBRL financial facts (CompanyFacts) for a specific company
financial-db sec companyfacts 0000320193

# Full sync for a single company (universe + filings + facts)
financial-db sec sync 0000320193

# Dry-run any command to preview without writing
financial-db sec sync 0000320193 --dry-run
```

**Targeted imports** (e.g., `--cik 0000320193`) are the primary workflow.
Full-universe sync (`financial-db sec sync-all --confirm`) is available but involves thousands of HTTP requests.

### Historical Bulk Ingestion (Phase 3.5/3.6/3.6.9)

For loading the complete SEC EDGAR universe from API-based bulk ingestion:

```bash
# Dry run to validate setup
financial-db sec bulk-ingest --dry-run

# Full bulk ingestion (API-based, processes all companies)
financial-db sec bulk-ingest --confirm

# Process with limit for testing
financial-db sec bulk-ingest --limit 100 --confirm

# Resume from checkpoint after interruption
financial-db sec bulk-ingest --checkpoint-file ./data/checkpoints/sec_bulk/full_universe_checkpoint.json --confirm
```

**Bulk ingestion options:**
| Option | Description |
|--------|-------------|
| `--limit N` | Process only first N companies |
| `--checkpoint-file` | Checkpoint file for resumability |
| `--dry-run` | Validate without writing |
| `--verbose` | Detailed logging |
| `--confirm` | Required for full runs |
| `--api-mode` | Use SEC API for ingestion (default) |

**Features:**
- **Memory efficient**: Streaming JSON parser (ijson) for large responses
- **Checkpoint/resume**: Atomic checkpoints saved every 30s or every 500 facts
- **Idempotent**: Re-running produces zero duplicates
- **Full history**: No date filtering - ingests ALL historical data from first filing
- **Network resilient**: Infinite retries with 10s intervals, 429/5xx/404 backoff
- **Graceful shutdown**: SIGINT/SIGTERM handlers save checkpoint and exit cleanly
- **Crash recovery**: Resume from last checkpoint without duplicates
- **Batch inserts**: 500 facts per transaction for 50%+ performance improvement
- **~56 hours** for complete SEC universe (~10,000 companies)

**Performance (validated):**
| Metric | Value (608 companies) | Extrapolated (10,388) |
|--------|-----------------------|----------------------|
| Time | ~51 min | ~14.5 hours |
| Facts inserted | ~12.3M | ~213M |
| Filings inserted | ~130K | ~2.2M |
| Database size | ~10 GB | ~170–200 GB |
| Avg time/company | ~5.0s | ~5.0s (network bound) |

### Stress Test Results (Phase 3.8)

A 608-company stress test was run and validated. Results:

- Companies processed: 608 (587 inserted, 21 updated)
- Filings inserted: 129,974
- Financial facts inserted: 12,343,979
- Errors: 10 (all expected `404` for non-XBRL filers: closed-end funds, ADRs, royalty trusts)
- Elapsed: ~51 minutes
- Integrity audit: zero duplicates/orphans (see `docs/validation_report.md`)
- Historical coverage: major filers back to 2009 (see `scripts/verify_history.sql`)

Full universe command:

```bash
SEC_USER_AGENT="YourApp/1.0 you@example.com" \
.venv/bin/python -m financial_database.cli sec bulk-ingest --confirm
```

Resume from an interrupted run with the same command (the checkpoint is
source-aware and resumes automatically). Use `--force` to reset progress.

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Database Schema Details](docs/database.md)
- [Data Sources and Providers](docs/data-sources.md)

## Development

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run tests with coverage
python -m pytest tests/ --cov=src

# Run specific test module
python -m pytest tests/unit/test_prices.py

# Run SEC provider tests
python -m pytest tests/unit/test_sec_*.py
```

### Adding Migrations

1. Create a new SQL file in `db/migrations/` with the next sequential number
2. Add your DDL statements
3. The migration system will automatically apply new migrations

## Disclaimer

This project was developed with the assistance of AI tools for debugging, error detection, and code optimization. While AI assistance was used, all code has been reviewed, tested, and verified by human developers to ensure correctness and quality.