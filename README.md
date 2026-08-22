# Financial Database

A PostgreSQL-based financial data warehouse designed to store and manage various types of financial data including company information, securities listings, prices, dividends, splits, financial facts (fundamentals), filings, raw documents, and import audit trails.

## Features

- Normalized schema for financial data
- Support for multiple data providers
- Full provenance tracking with source identifiers
- Audit trails for all import operations
- Flexible design to accommodate various financial data types
- Constraint-based data integrity
- Indexed for common query patterns

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
```

### Adding Migrations

1. Create a new SQL file in `db/migrations/` with the next sequential number
2. Add your DDL statements
3. The migration system will automatically apply new migrations

## License

This project is licensed under the MIT License.