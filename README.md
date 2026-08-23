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

## License

This project is licensed under the MIT License.