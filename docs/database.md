# Database Schema Reference

This document provides detailed information about each table in the financial database schema, including columns, data types, constraints, and relationships.

## Table Index

1. [companies](#companies)
2. [company_identifiers](#company_identifiers)
3. [company_listings](#company_listings)
4. [exchanges](#exchanges)
5. [data_providers](#data_providers)
6. [filings](#filings)
7. [financial_facts](#financial_facts)
8. [prices](#prices)
9. [dividends](#dividends)
10. [splits](#splits)
11. [raw_documents](#raw_documents)
12. [import_runs](#import_runs)

---

## companies

Stores basic information about legal entities (companies).

### Columns

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| id | UUID | NO | gen_random_uuid() | Primary key |
| legal_name | VARCHAR | NO |  | Official registered name of the company |
| country | VARCHAR | YES |  | Country of incorporation or primary operations |
| sector | VARCHAR | YES |  | Business sector classification |
| industry | VARCHAR | YES |  | Industry sub-classification |
| currency | VARCHAR | YES | 'USD'::character varying | Default currency for financial reporting |
| website | VARCHAR | YES |  | Company website URL |
| is_active | BOOLEAN | YES | true | Whether the company is currently active |
| created_at | TIMESTAMPTZ | NO | now() | Record creation timestamp |
| updated_at | TIMESTAMPTZ | NO | now() | Record last update timestamp |

### Constraints

- Primary Key: `companies_pkey` (id)
- No ticker column (tickers are stored in the company_listings table)

### Indexes

- Implicit primary key index on id

---

## company_identifiers

Stores external identifiers for companies (CIK, FIGI, ISIN, etc.).

### Columns

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| id | UUID | NO | gen_random_uuid() | Primary key |
| company_id | UUID | NO |  | Foreign key to companies(id) |
| identifier_type | VARCHAR | NO |  | Type of identifier (CIK, FIGI, ISIN, etc.) |
| identifier_value | VARCHAR | NO |  | The actual identifier value |
| is_primary | BOOLEAN | YES | false | Whether this is the primary identifier for the company |
| created_at | TIMESTAMPTZ | NO | now() | Record creation timestamp |
| updated_at | TIMESTAMPTZ | NO | now() | Record last update timestamp |

### Constraints

- Primary Key: `company_identifiers_pkey` (id)
- Foreign Key: `company_identifiers_company_id_fkey` references companies(id)
- Unique Constraint: Unique combination of company_id and identifier_type
- Check Constraint: Valid identifier types (enforced at application level)

### Indexes

- Primary key index on id
- Foreign key index on company_id
- Unique index on (company_id, identifier_type)

---

## company_listings

Represents a company's listing on a specific exchange.

### Columns

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| id | UUID | NO | gen_random_uuid() | Primary key |
| company_id | UUID | NO |  | Foreign key to companies(id) |
| exchange_id | UUID | NO |  | Foreign key to exchanges(id) |
| ticker | VARCHAR | NO |  | Stock ticker symbol |
| share_class | VARCHAR | YES |  | Share class designation (e.g., 'A', 'B') |
| listing_date | DATE | YES |  | Date when the security was first listed |
| delisting_date | DATE | YES |  | Date when the security was removed from listing |
| is_primary | BOOLEAN | YES | false | Whether this is the primary listing for the company |
| is_active | BOOLEAN | YES |  | Computed: true if delisting_date is NULL |
| created_at | TIMESTAMPTZ | NO | now() | Record creation timestamp |
| updated_at | TIMESTAMPTZ | NO | now() | Record last update timestamp |

### Constraints

- Primary Key: `company_listings_pkey` (id)
- Foreign Keys:
  - `company_listings_company_id_fkey` references companies(id)
  - `company_listings_exchange_id_fkey` references exchanges(id)
- Unique Constraint: `company_listings_company_id_exchange_id_share_class_listing_key` on (company_id, exchange_id, share_class, listing_date)
- Exclusion Constraint: Prevents overlapping periods for the same company, exchange, and share class using tsrange

### Indexes

- Primary key index on id
- Foreign key indexes on company_id and exchange_id
- Unique index on the combination above
- Indexes supporting the exclusion constraint

---

## exchanges

Contains information about stock exchanges and trading venues.

### Columns

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| id | UUID | NO | gen_random_uuid() | Primary key |
| code | VARCHAR | NO |  | Exchange identifier (e.g., NYSE, NASDAQ, LSE) |
| name | VARCHAR | NO |  | Full exchange name |
| mic | VARCHAR | YES |  | Market Identifier Code (ISO 10383) |
| country | VARCHAR | YES |  | Country where the exchange is located |
| timezone | VARCHAR | YES |  | Primary timezone of the exchange |
| created_at | TIMESTAMPTZ | NO | now() | Record creation timestamp |
| updated_at | TIMESTAMPTZ | NO | now() | Record last update timestamp |

### Constraints

- Primary Key: `exchanges_pkey` (id)
- Unique Constraint: Unique on code
- Unique Constraint: Unique on mic (when not null)

### Indexes

- Primary key index on id
- Unique index on code
- Unique index on mic

---

## data_providers

Tracks sources of financial data.

### Columns

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| id | UUID | NO | gen_random_uuid() | Primary key |
| name | VARCHAR | NO |  | Provider name (e.g., 'SEC', 'Bloomberg', 'Refinitiv') |
| type | VARCHAR | NO |  | Provider type: 'price', 'fundamental', 'sec', 'exchange', etc. |
| priority | INTEGER | YES | 1 | Priority for conflicting data (higher = preferred) |
| active | BOOLEAN | YES | true | Whether the provider is currently active |
| created_at | TIMESTAMPTZ | NO | now() | Record creation timestamp |
| updated_at | TIMESTAMPTZ | NO | now() | Record last update timestamp |

### Constraints

- Primary Key: `data_providers_pkey` (id)
- Check Constraint: Valid provider types (enforced at application level)

### Indexes

- Primary key index on id
- Index on type for filtering by provider type

---

## filings

Stores information about regulatory filings (10-K, 10-Q, 8-K, etc.).

### Columns

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| id | UUID | NO | gen_random_uuid() | Primary key |
| company_id | UUID | NO |  | Foreign key to companies(id) |
| provider_id | UUID | NO |  | Foreign key to data_providers(id) |
| form | VARCHAR | NO |  | Form type (e.g., '10-K', '10-Q', '8-K') |
| accession_number | VARCHAR | NO |  | Unique identifier from the source system |
| filing_date | DATE | NO |  | Date the filing was submitted |
| period_start | DATE | YES |  | Start of reporting period (NULL for instant/point-in-time) |
| period_end | DATE | NO |  | End of reporting period |
| fiscal_year | INTEGER | YES |  | Fiscal year of the reporting period |
| fiscal_period | VARCHAR | YES |  | Fiscal period (e.g., 'FY', 'Q1', 'Q2', 'Q3', 'H1', 'H2') |
| filing_url | VARCHAR | YES |  | URL to access the filing |
| raw_document_id | UUID | YES |  | Foreign key to raw_documents(id) |
| is_amended | BOOLEAN | YES | false | Whether this filing amends a previous filing |
| amended_by_filing_id | UUID | YES |  | If this filing is amended, points to the amending filing |
| created_at | TIMESTAMPTZ | NO | now() | Record creation timestamp |
| updated_at | TIMESTAMPTZ | NO | now() | Record last update timestamp |

### Constraints

- Primary Key: `filings_pkey` (id)
- Foreign Keys:
  - `filings_company_id_fkey` references companies(id)
  - `filings_provider_id_fkey` references data_providers(id)
  - `filings_raw_document_id_fkey` references raw_documents(id)
  - `filings_amended_by_filing_id_fkey` references filings(id)
- Unique Constraint: Unique on (provider_id, accession_number)
- Check Constraint: period consistency (period_start IS NULL OR period_start <= period_end)

### Indexes

- Primary key index on id
- Foreign key indexes on company_id, provider_id, raw_document_id
- Unique index on (provider_id, accession_number)
- Index on filing_date for time-based queries
- Composite index on (company_id, period_start, period_end) for period lookups

---

## financial_facts

Normalized storage for financial statement data (both instant and duration facts).

### Columns

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| id | UUID | NO | gen_random_uuid() | Primary key |
| company_id | UUID | NO |  | Foreign key to companies(id) |
| filing_id | UUID | YES |  | Foreign key to filings(id) |
| provider_id | UUID | NO |  | Foreign key to data_providers(id) |
| concept | VARCHAR | NO |  | Financial concept (e.g., 'Revenue', 'Assets', 'NetIncomeLoss') |
| value | NUMERIC | NO |  | Numerical value of the fact |
| unit | VARCHAR | NO |  | Unit of measurement (e.g., 'USD', 'shares', 'USD/share') |
| period_start | DATE | YES |  | Start of period (NULL for instant facts) |
| period_end | DATE | NO |  | End of period |
| fiscal_year | INTEGER | NO |  | Fiscal year |
| fiscal_period | VARCHAR | NO |  | Fiscal period (e.g., 'FY', 'Q1', 'Q2', 'Q3', 'H1', 'H2') |
| form | VARCHAR | YES |  | Form type (e.g., '10-K', '10-Q') |
| source_id | VARCHAR | YES |  | Provider-specific fact identifier |
| filing_date | DATE | NO |  | Date of associated filing |
| created_at | TIMESTAMPTZ | NO | now() | Record creation timestamp |
| updated_at | TIMESTAMPTZ | NO | now() | Record last update timestamp |

### Constraints

- Primary Key: `financial_facts_pkey` (id)
- Foreign Keys:
  - `financial_facts_company_id_fkey` references companies(id)
  - `financial_facts_filing_id_fkey` references filings(id)
  - `financial_facts_provider_id_fkey` references data_providers(id)
- Unique Constraint: Unique on (company_id, concept, period_start, period_end, filing_id, source_id)
- Check Constraint: `chk_financial_facts_period` ensures period_start IS NULL OR period_start <= period_end

### Indexes

- Primary key index on id
- Foreign key indexes on company_id, filing_id, provider_id
- Unique index on the combination above
- Index on concept for concept-based lookups
- Index on (period_start, period_end) for period-based queries
- Index on (fiscal_year, fiscal_period) for fiscal period queries
- Composite index on (company_id, concept) for company-concept lookups
- Index on filing_id for joining with filings
- Index on provider_id for provider-based filtering

---

## prices

Historical price and volume data for securities.

### Columns

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| id | UUID | NO | gen_random_uuid() | Primary key |
| listing_id | UUID | NO |  | Foreign key to company_listings(id) |
| provider_id | UUID | NO |  | Foreign key to data_providers(id) |
| price_date | DATE | NO |  | Date of the price record |
| open | NUMERIC | NO |  | Opening price |
| high | NUMERIC | NO |  | Highest price during the day |
| low | NUMERIC | NO |  | Lowest price during the day |
| close | NUMERIC | NO |  | Closing price |
| adjusted_close | NUMERIC | YES |  | Closing price adjusted for dividends and splits |
| volume | BIGINT | NO |  | Trading volume |
| currency | VARCHAR | NO | 'USD'::character varying | Currency of the price |
| source_id | VARCHAR | YES |  | Provider-specific identifier for the price record |
| created_at | TIMESTAMPTZ | NO | now() | Record creation timestamp |
| updated_at | TIMESTAMPTZ | NO | now() | Record last update timestamp |

### Constraints

- Primary Key: `prices_pkey` (id)
- Foreign Keys:
  - `prices_listing_id_fkey` references company_listings(id)
  - `prices_provider_id_fkey` references data_providers(id)
- Unique Constraint: Unique on (listing_id, price_date, provider_id)
- Check Constraints:
  - `chk_prices_open_non_negative`: open >= 0
  - `chk_prices_high_non_negative`: high >= 0
  - `chk_prices_low_non_negative`: low >= 0
  - `chk_prices_close_non_negative`: close >= 0
  - `chk_prices_adjusted_close_non_negative`: adjusted_close >= 0 (when not null)
  - `chk_prices_volume_non_negative`: volume >= 0

### Indexes

- Primary key index on id
- Foreign key indexes on listing_id and provider_id
- Unique index on (listing_id, price_date, provider_id)
- Index on price_date for time-series queries
- Individual indexes on each OHLCV column for range queries
- Composite index on (listing_id, price_date DESC) for latest-first queries

---

## dividends

Tracks dividend declarations and payments.

### Columns

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| id | UUID | NO | gen_random_uuid() | Primary key |
| listing_id | UUID | NO |  | Foreign key to company_listings(id) |
| provider_id | UUID | NO |  | Foreign key to data_providers(id) |
| ex_dividend_date | DATE | YES |  | Date when stock trades without the dividend |
| record_date | DATE | YES |  | Date when shareholders are determined |
| payment_date | DATE | YES |  | Date when dividend is paid |
| amount | NUMERIC | NO |  | Dividend amount per share |
| currency | VARCHAR | NO | 'USD'::character varying | Currency of the dividend amount |
| source_id | VARCHAR | YES |  | Provider-specific identifier for the dividend record |
| created_at | TIMESTAMPTZ | NO | now() | Record creation timestamp |
| updated_at | TIMESTAMPTZ | NO | now() | Record last update timestamp |

### Constraints

- Primary Key: `dividends_pkey` (id)
- Foreign Keys:
  - `dividends_listing_id_fkey` references company_listings(id)
  - `dividends_provider_id_fkey` references data_providers(id)
- Unique Constraint: Unique on (listing_id, ex_dividend_date, provider_id, source_id)
- Check Constraints:
  - `chk_dividends_amount`: amount >= 0
  - `chk_dividends_dates`: (ex_dividend_date IS NULL OR record_date IS NULL OR ex_dividend_date <= record_date)

### Indexes

- Primary key index on id
- Foreign key indexes on listing_id and provider_id
- Unique index on (listing_id, ex_dividend_date, provider_id, source_id)
- Index on ex_dividend_date for dividend date queries
- Composite index on (listing_id, ex_dividend_date DESC) for latest-first queries

---

## splits

Stock split and spin-off events.

### Columns

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| id | UUID | NO | gen_random_uuid() | Primary key |
| listing_id | UUID | NO |  | Foreign key to company_listings(id) |
| provider_id | UUID | NO |  | Foreign key to data_providers(id) |
| execution_date | DATE | NO |  | Date when the split becomes effective |
| numerator | INTEGER | NO |  | Split ratio numerator (e.g., 2 in 2-for-1) |
| denominator | INTEGER | NO |  | Split ratio denominator (e.g., 1 in 2-for-1) |
| source_id | VARCHAR | YES |  | Provider-specific identifier for the split record |
| created_at | TIMESTAMPTZ | NO | now() | Record creation timestamp |
| updated_at | TIMESTAMPTZ | NO | now() | Record last update timestamp |

### Constraints

- Primary Key: `splits_pkey` (id)
- Foreign Keys:
  - `splits_listing_id_fkey` references company_listings(id)
  - `splits_provider_id_fkey` references data_providers(id)
- Unique Constraint: Unique on (listing_id, execution_date, provider_id, source_id)
- Check Constraint: `chk_splits_positive` ensures (numerator > 0 AND denominator > 0)

### Indexes

- Primary key index on id
- Foreign key indexes on listing_id and provider_id
- Unique index on (listing_id, execution_date, provider_id, source_id)
- Index on execution_date for split date queries
- Composite index on (listing_id, execution_date DESC) for latest-first queries

---

## raw_documents

Metadata for preserved raw data files (actual files stored in filesystem/object storage).

### Columns

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| id | UUID | NO | gen_random_uuid() | Primary key |
| provider_id | UUID | NO |  | Foreign key to data_providers(id) |
| source_identifier | VARCHAR | NO |  | Original identifier from source system (e.g., SEC accession number) |
| storage_path | VARCHAR | NO |  | Filesystem path or object key where file is stored |
| checksum | VARCHAR | YES |  | SHA256 hex digest of file contents |
| content_type | VARCHAR | YES |  | MIME type of the file (e.g., 'text/plain', 'application/pdf') |
| retrieved_at | TIMESTAMPTZ | NO | now() | Timestamp when file was retrieved |
| metadata | JSONB | YES | '{}'::jsonb | Additional provider-specific metadata |
| is_processed | BOOLEAN | YES | false | Whether the file has been processed |
| created_at | TIMESTAMPTZ | NO | now() | Record creation timestamp |
| updated_at | TIMESTAMPTZ | NO | now() | Record last update timestamp |

### Constraints

- Primary Key: `raw_documents_pkey` (id)
- Foreign Key: `raw_documents_provider_id_fkey` references data_providers(id)
- Unique Constraint: Unique on (provider_id, source_identifier)

### Indexes

- Primary key index on id
- Foreign key index on provider_id
- Unique index on (provider_id, source_identifier)
- Index on is_processed for filtering unprocessed documents
- Index on retrieved_at for time-based queries

---

## import_runs

Audit trail for data import/ETL operations.

### Columns

| Column Name | Data Type | Nullable | Default | Description |
|-------------|-----------|----------|---------|-------------|
| id | UUID | NO | gen_random_uuid() | Primary key |
| provider_id | UUID | NO |  | Foreign key to data_providers(id) |
| pipeline | VARCHAR | NO |  | Name of the data pipeline (e.g., 'companies', 'filings', 'prices') |
| status | VARCHAR | NO | 'running'::character varying | Current status: 'running', 'success', 'failed', 'partial' |
| records_processed | INTEGER | YES | 0 | Total records processed in this run |
| records_inserted | INTEGER | YES | 0 | Records newly inserted |
| records_updated | INTEGER | YES | 0 | Records updated |
| records_skipped | INTEGER | YES | 0 | Records skipped due to duplicates or errors |
| errors | JSONB | YES | '{}'::jsonb | Structured error information |
| started_at | TIMESTAMPTZ | NO | now() | Timestamp when the import started |
| finished_at | TIMESTAMPTZ | YES |  | Timestamp when the import completed |
| duration_seconds | INTEGER | YES |  | Total execution time in seconds |
| created_at | TIMESTAMPTZ | NO | now() | Record creation timestamp |

### Constraints

- Primary Key: `import_runs_pkey` (id)
- Foreign Key: `import_runs_provider_id_fkey` references data_providers(id)
- Check Constraint: `chk_import_runs_status` ensures status is one of: 'running', 'success', 'failed', 'partial'

### Indexes

- Primary key index on id
- Foreign key index on provider_id
- Index on status for filtering by run status
- Index on started_at for time-based queries
- Composite index on (provider_id, pipeline) for provider-pipeline queries

---

## Relationships Summary

```
companies 1 ──< company_identifiers
companies 1 ──< company_listings >── 1 exchanges
companies 1 ──< financial_facts
companies 1 ──< filings
data_providers 1 ──< company_identifiers
data_providers 1 ──< filings
data_providers 1 ──< financial_facts
data_providers 1 ──< prices
data_providers 1 ──< dividends
data_providers 1 ──< splits
data_providers 1 ──< raw_documents
data_providers 1 ──< import_runs
exchanges 1 ──< company_listings
filings 1 ──< raw_documents (optional)
filings 1 ──< filings (self-referential for amendments)
filings 1 ──< financial_facts (optional)
company_listings 1 ──< prices
company_listings 1 ──< dividends
company_listings 1 ──< splits
```

*Note: 1 = one, > = many, < = many, ──< = one-to-many*

---

## Naming Conventions

- **Tables**: Snake_case, plural nouns (e.g., `financial_facts`)
- **Columns**: Snake_case, descriptive names
- **Primary Keys**: Always named `id` with UUID type
- **Foreign Keys**: `{table}_{column}_fkey` (e.g., `financial_facts_company_id_fkey`)
- **Unique Constraints**: Descriptive names indicating the unique combination
- **Check Constraints**: `chk_{table}_{description}` (e.g., `chk_prices_volume_non_negative`)
- **Indexes**: `idx_{table}_{columns}` or descriptive names for special indexes
- **Sequences**: Not used (UUIDs are generated via `gen_random_uuid()`)

---

## Data Types Rationale

- **UUID**: Used for all primary keys to support distributed systems and prevent key collisions
- **VARCHAR**: Used for text fields with appropriate length limits based on expected data
- **DATE**: Used for calendar dates without time zone
- **TIMESTAMPTZ**: Used for timestamps with time zone awareness (all set to `now()` by default)
- **NUMERIC**: Used for precise decimal values (prices, financial amounts) with specified precision/scale
- **INTEGER**: Used for whole numbers, counts, and small identifiers
- **BIGINT**: Used for potentially large counts (trading volume)
- **BOOLEAN**: Used for true/false flags
- **JSONB**: Used for flexible, structured metadata storage

---

## Integrity Validation

Before the full SEC universe load, run the integrity audit
(`scripts/integrity_audit.sql`) against `financial_database`. All checks must
return zero offending rows except "companies with no facts/filings" (expected
for non-XBRL filers such as closed-end funds, ADRs, and royalty trusts).

The audit covers:

- Duplicate companies (legal_name + country, or same CIK on multiple companies)
- Duplicate company identifiers / listings / filings / financial facts
- Orphaned facts, filings, and listings
- Facts with NULL value
- Companies with no facts / filings / identifiers
- Facts without provenance (missing `provider_id`, `filing_id`, or `source_id`)
- Facts referencing a non-existent filing

Fact provenance notes:

- Every fact has `provider_id` and `source_id` (the accession number is embedded
  in `source_id`).
- `filing_id` links facts to their source filing where one is stored. Facts from
  forms not persisted as filings (e.g. `8-K`) legitimately have a NULL
  `filing_id`.
- The `financial_facts` unique constraint is defined `NULLS NOT DISTINCT`
  (migration `0019`) so facts with a NULL `filing_id` still deduplicate
  correctly.