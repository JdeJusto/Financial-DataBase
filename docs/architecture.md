# Financial Database Architecture

## Overview

The Financial Database is designed as a normalized, extensible PostgreSQL database for storing and managing financial data from various sources. The architecture emphasizes data integrity, provenance tracking, and flexibility to accommodate different financial data types and reporting frequencies.

## Design Principles

1. **Normalization**: Data is structured to minimize redundancy and dependency
2. **Provenance**: Every data point traces back to its source provider and original document
3. **Extensibility**: New data types and providers can be added without schema changes
4. **Auditability**: Complete import history and data lineage tracking
5. **Performance**: Strategic indexing for common query patterns

## Core Components

### 1. Company and Security Master Data

- **companies**: Core entity representing legal entities
- **company_identifiers**: External identifiers (CIK, FIGI, ISIN, etc.)
- **exchanges**: Stock exchanges and trading venues
- **company_listings**: Junction table linking companies to exchanges with ticker information

### 2. Data Provenance Layer

- **data_providers**: Sources of financial data (SEC, Bloomberg, Reuters, etc.)
- Tracks provider type (price, fundamental, sec, etc.) for appropriate routing

### 3. Financial Data Storage

#### Time-Series Data
- **prices**: OHLCV data with provider attribution
- **dividends**: Dividend declarations and payments
- **splits**: Stock split and spin-off events

#### Statement Data
- **financial_facts**: Normalized financial statement line items
  - Supports both instant (balance sheet) and duration (income statement) facts
  - Period handling with nullable start date for instant facts
  - Full concept, unit, and source attribution

#### Event Data
- **filings**: Regulatory filings (10-K, 10-Q, 8-K, etc.)
- Links to source documents and companies

### 4. Raw Data Preservation

- **raw_documents**: Metadata for original source files
  - Actual files stored in filesystem/object storage
  - Database stores only metadata, checksums, and storage paths
  - Enables reproducibility and audit trails

### 5. Import and Audit Infrastructure

- **import_runs**: ETL/import audit trail
  - Tracks pipeline execution, success/failure states
  - Records processed, inserted, updated, and skipped
  - Error collection and timing information

### 6. SEC EDGAR Provider Architecture

The SEC provider implements a production-quality ingestion pipeline following the provider abstraction:

```
SEC EDGAR
    ↓
Raw storage (filesystem)
    ↓
Parser (XBRL/JSON → domain models)
    ↓
Validation (business rules, constraints)
    ↓
Normalization (CIK, accession, exchange, units)
    ↓
Repository (idempotent upserts)
    ↓
PostgreSQL
```

#### Provider Isolation

- **src/financial_database/providers/sec/** - All SEC-specific logic isolated
- **src/financial_database/providers/base.py** - Abstract base classes
- Database repositories know nothing about SEC HTTP details
- SEC client contains no SQL business logic

#### SEC Client (`client.py`)

- HTTPS only with explicit User-Agent (required by SEC)
- Configurable timeouts, retries with exponential backoff
- Respects HTTP 429 and Retry-After headers
- Conservative rate limiting (10 req/s default)
- Structured logging without secrets
- Raw response storage with SHA-256 checksums

#### SEC Models (`models.py`)

- `SECCompany` - Company universe from tickers exchange reference
- `SECSubmissions` / `SECFiling` - Filing metadata (10-K, 10-Q, 8-K, 20-F, 40-F, 6-K)
- `SECCompanyFacts` / `SECCompanyFact` / `SECCompanyFactValue` - XBRL parsed facts
- CIK normalization (10-digit zero-padded canonical form)
- Accession number normalization (dashes removed)
- Exchange mapping (SEC names → internal codes with MIC)

#### SEC Parser (`parser.py`)

- Normalizes SEC data into domain models (`ParsedCompany`, `ParsedFiling`, `ParsedFinancialFact`)
- Preserves XBRL namespace + concept identity (not collapsed)
- Preserves original SEC units (USD, shares, USD/shares, pure, etc.)
- Correctly distinguishes instant vs duration facts
- Preserves frame information (CY2023, CY2023Q1, etc.)
- Preserves fiscal period metadata (FY, Q1, Q2, Q3, Q4)
- Validation before insertion

#### SEC Importer (`importer.py`)

- Idempotent operations using database unique constraints
- Raw document tracking with checksums (preserves history on content change)
- Import run audit trail for every pipeline execution
- Restatement support: original + amended facts coexist via filing_id/source_id
- Incremental ingestion via raw_documents and source identifiers
- Error handling with per-record recovery where safe

## Key Architectural Decisions

### UUID Primary Keys
- All tables use UUIDs as primary keys for distributed system friendliness
- Prevents key collisions when merging data from multiple sources
- Generated using `gen_random_uuid()` for performance

### Provider Attribution
- Every major data table includes a `provider_id` foreign key
- Enables tracking data lineage and resolving conflicts between providers
- Provider-specific source IDs maintained where applicable

### Temporal Data Handling
- Financial facts support both instant and period data through nullable `period_start`
- Check constraints ensure temporal validity (`period_start <= period_end` or `period_start IS NULL`)
- Import runs track execution timing for performance monitoring and SLA tracking

### Constraint-Based Integrity
- Check constraints enforce business rules at the database level:
  - Non-negative prices and volumes
  - Valid date relationships
  - Status enumeration validation
  - Positive numerators/denominators for splits

### Indexing Strategy
- Primary key indexes on all UUID columns
- Foreign key indexes for join performance
- Composite indexes for common query patterns:
  - Company+concept+period for financial facts retrieval
  - Listing+date for price/volume lookups
  - Provider-based indexes for data source isolation
  - Status and timing indexes for import audit queries

### Extensibility Patterns
- JSONB metadata fields for flexible attribute storage
- VARCHAR source IDs for provider-specific identifiers
- Design allows adding new data types by following existing patterns
- Migration system supports schema evolution

## Data Flow

1. **Ingestion**: External data providers submit data through ETL pipelines
2. **Staging**: Raw files preserved in filesystem/object storage with database metadata
3. **Processing**: Data validated, normalized, and inserted into appropriate tables
4. **Audit**: Import runs record processing statistics and any errors
5. **Consumption**: Applications query normalized data with full provenance

### SEC-Specific Data Flow

1. **Universe**: Fetch company tickers exchange reference → upsert companies, identifiers, listings, exchanges
2. **Submissions**: For each CIK, fetch submissions metadata → upsert filings with raw_document links
3. **CompanyFacts**: For each CIK, fetch XBRL CompanyFacts → parse facts → validate → insert financial_facts
4. **Provenance**: Every step creates raw_documents entries and import_runs records

## Security Considerations

- Role-based access control recommended for production deployment
- Connection SSL/TLS encryption
- Regular backups and point-in-time recovery
- Audit trail preserves all changes for compliance
- SEC_USER_AGENT from environment (never hardcoded, never logged)
- Raw SEC responses never committed to Git

## Scalability Considerations

- Partitioning strategy can be implemented for large time-series tables
- Read replicas for query distribution
- Connection pooling for concurrent access
- Archiving strategy for historical data beyond active retention period
- SEC ingestion is intentionally conservative (rate limited, sequential)