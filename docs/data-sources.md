# Data Sources and Providers

This document describes the data source model used in the financial database, including provider types, source identification, and data provenance tracking.

## Provider Model

The financial database uses a provider-centric approach to track the origin and reliability of financial data. Each data point in the system can be traced back to its originating provider, enabling data lineage tracking, conflict resolution, and quality assessment.

### Provider Attributes

Each data provider in the system has the following attributes:

- **id**: UUID primary key
- **name**: Human-readable provider name (e.g., "SEC EDGAR", "Bloomberg", "Refinitiv")
- **type**: Categorical provider type that determines what kind of data the provider supplies
- **priority**: Integer value used to resolve conflicts when multiple providers supply the same data point (higher priority wins)
- **active**: Boolean flag indicating whether the provider is currently active
- **created_at/updated_at**: Audit timestamps

### Provider Types

The system defines several standard provider types, though the schema allows for extension:

| Provider Type | Description | Typical Data Supplied |
|---------------|-------------|-----------------------|
| `price` | Market data providers | Stock prices, volumes, OHLCV data |
| `fundamental` | Financial statement providers | Balance sheet, income statement, cash flow data |
| `sec` | U.S. Securities and Exchange Commission | Regulatory filings (10-K, 10-Q, 8-K, etc.), company metadata |
| `exchange` | Stock exchanges | Official listing data, trading status, corporate actions |
| `registry` | Identifier registries | FIGI, ISIN, CUSIP, LEI mappings |
| `analyst` | Financial analysts | Estimates, ratings, target prices |
| `economic` | Economic data providers | Macroeconomic indicators, interest rates, GDP data |
| `news` | News aggregators | Press releases, news articles, sentiment data |
| `rating` | Credit rating agencies | Credit ratings, risk assessments |
| `custom` | User-defined sources | Proprietary data, internal calculations, manual entries |

### Source Identification

Each provider may use different identification schemes for the same entities. The database accommodates this through:

1. **Provider-specific source IDs**: Many tables include an optional `source_id` VARCHAR column that stores the provider's own identifier for a record
2. **Cross-reference tables**: The `company_identifiers` table maintains mappings between different identification systems
3. **Raw document preservation**: The `raw_documents` table preserves the original identifiers from source systems

### Data Provenance

Every major data table in the system includes provenance tracking:

1. **Provider Attribution**: All core data tables (`financial_facts`, `prices`, `dividends`, `splits`, `filings`) include a `provider_id` foreign key
2. **Filing Attribution**: Financial facts can be linked to their source filing via the `filing_id` foreign key
3. **Raw Document Linking**: Filings can optionally reference the original raw document via `raw_document_id`
4. **Import Audit Trail**: The `import_runs` table tracks when and how data was loaded into the system

### Conflict Resolution

When multiple providers supply conflicting data for the same entity (e.g., different prices for the same security on the same date), the system uses:

1. **Provider Priority**: Each provider has a priority level; higher priority data wins in conflicts
2. **Timestamp Preference**: For same-priority providers, more recent data may be preferred
3. **Source Tracking**: All conflicting values are preserved in the database with full provenance, allowing applications to implement custom conflict resolution logic

### SEC EDGAR Provider Details

The SEC EDGAR provider is a first-class provider implementation with a complete ingestion pipeline.

#### SEC Provider Registration

```sql
INSERT INTO data_providers (name, type, display_name, base_url, rate_limit_per_second, is_active)
VALUES ('SEC EDGAR', 'sec', 'SEC EDGAR', 'https://www.sec.gov', 10.0, TRUE)
ON CONFLICT (name) DO NOTHING;
```

The migration `0015_sec_provider_seed.sql` seeds this provider and common SEC exchanges.

#### SEC Data Sources

| Endpoint | Data | Database Tables |
|----------|------|-----------------|
| `/files/company_tickers_exchange.json` | Company universe (CIK, name, ticker, exchange) | `companies`, `company_identifiers`, `company_listings`, `exchanges` |
| `/submissions/CIK##########.json` | Filing metadata (accession, form, dates, periods) | `filings`, `raw_documents` |
| `/api/xbrl/companyfacts/CIK##########.json` | XBRL financial facts (concepts, values, periods) | `financial_facts`, `raw_documents` |

#### SEC Access Requirements

- **User-Agent**: Required by SEC. Must be descriptive with contact info.
  - Set via `SEC_USER_AGENT` environment variable
  - Format: `"ApplicationName/Version ContactEmail"`
  - Example: `"financial-database/0.1 contact@example.com"`
- **Rate Limits**: SEC enforces limits. Client implements conservative 10 req/s default.
- **HTTPS Only**: All requests use HTTPS.

#### SEC Data Normalization

| SEC Field | Normalization | Database Storage |
|-----------|---------------|------------------|
| CIK | Zero-padded to 10 digits | `company_identifiers.identifier_value` (type=CIK) |
| Accession Number | Dashes removed | `filings.accession_number`, `financial_facts.source_id` |
| Exchange | Mapped to internal code + MIC | `exchanges.code`, `exchanges.mic` |
| Units | Preserved exactly | `financial_facts.unit` |
| Namespace + Concept | Preserved as-is | `financial_facts.concept` (namespace in JSONB metadata) |
| Instant/Duration | `period_start` NULL for instant | `financial_facts.period_start` |
| Frame | Preserved if available | `financial_facts` metadata JSONB |
| Fiscal Period | Preserved (FY, Q1-Q4, H1, H2) | `financial_facts.fiscal_period` |

#### Restatement Handling

The same economic period may appear in multiple filings (original, amended, restated). The database allows coexistence via:

- Unique constraint on `(company_id, concept, period_start, period_end, filing_id, source_id)`
- `filing_id` links to specific filing (original vs amended)
- `source_id` includes accession + concept + period for uniqueness
- `is_amended` flag on filings tracks amendment chain

#### Incremental Ingestion

- Raw documents tracked by `(provider_id, source_identifier)` with SHA-256 checksum
- Content changes preserve previous version with timestamp
- Import runs record processed/inserted/updated/skipped counts
- Re-running pipeline only processes new/changed data

### Typical Provider Configurations

#### Market Data Providers
```sql
INSERT INTO data_providers (name, type, priority, active)
VALUES 
('NASDAQ', 'price', 100, true),
('NYSE', 'price', 100, true),
('Bloomberg', 'price', 80, true),
('Refinitiv', 'price', 80, true),
('IEX', 'price', 90, true);
```

#### Financial Statement Providers
```sql
INSERT INTO data_providers (name, type, priority, active)
VALUES 
('SEC', 'fundamental', 100, true),
('FactSet', 'fundamental', 80, true),
('S&P Capital IQ', 'fundamental', 80, true),
('Morningstar', 'fundamental', 70, true);
```

#### Regulatory Data Providers
```sql
INSERT INTO data_providers (name, type, priority, active)
VALUES 
('SEC EDGAR', 'sec', 100, true),
('SEC', 'sec', 100, true);  -- Legacy alias if needed
```

#### Exchange Providers
```sql
INSERT INTO data_providers (name, type, priority, active)
VALUES 
('NASDAQ', 'exchange', 100, true),
('NYSE', 'exchange', 100, true),
('LSE', 'exchange', 100, true),
('TSE', 'exchange', 100, true);
```

### Data Flow with Provenance

1. **Data Ingestion**: External provider sends data through an ETL pipeline
2. **Provider Validation**: System verifies provider exists and is active
3. **Raw Storage**: Original data file is stored in filesystem/object storage
4. **Metadata Recording**: `raw_documents` table records metadata about the original file
5. **Data Normalization**: Data is converted to the database's standard format
6. **Database Insertion**: Normalized data is inserted with `provider_id` and optional `source_id`
7. **Audit Recording**: `import_runs` table records the import operation statistics
8. **Conflict Detection**: System identifies any conflicts with existing data
9. **Resolution**: Conflicts resolved according to provider priority rules (configurable)
10. **Availability**: Data becomes available for querying with full provenance

### Querying with Provenance

Examples of how to query data with provenance information:

#### Get a financial fact with its provider
```sql
SELECT 
    ff.id,
    ff.concept,
    ff.value,
    ff.unit,
    dp.name as provider_name,
    dp.type as provider_type
FROM financial_facts ff
JOIN data_providers dp ON ff.provider_id = dp.id
WHERE ff.company_id = ? AND ff.concept = 'Revenue';
```

#### Get all prices for a security with provider information
```sql
SELECT 
    p.price_date,
    p.open,
    p.high,
    p.low,
    p.close,
    p.volume,
    dp.name as provider,
    p.source_id as provider_source_id
FROM prices p
JOIN data_providers dp ON p.provider_id = dp.id
WHERE p.listing_id = ?
ORDER BY p.price_date DESC;
```

#### Get a filing with its source document
```sql
SELECT 
    f.form,
    f.accession_number,
    f.filing_date,
    dp.name as provider,
    rd.source_identifier as original_id,
    rd.storage_path as file_location
FROM filings f
JOIN data_providers dp ON f.provider_id = dp.id
LEFT JOIN raw_documents rd ON f.raw_document_id = rd.id
WHERE f.company_id = ? AND f.form = '10-K'
ORDER BY f.filing_date DESC LIMIT 1;
```

#### Get SEC financial facts with filing provenance
```sql
SELECT 
    ff.concept,
    ff.value,
    ff.unit,
    ff.period_start,
    ff.period_end,
    ff.fiscal_year,
    ff.fiscal_period,
    f.form,
    f.accession_number,
    f.filing_date,
    rd.storage_path as raw_file
FROM financial_facts ff
JOIN filings f ON ff.filing_id = f.id
JOIN data_providers dp ON ff.provider_id = dp.id
LEFT JOIN raw_documents rd ON f.raw_document_id = rd.id
WHERE ff.company_id = ? AND dp.name = 'SEC EDGAR'
ORDER BY ff.fiscal_year DESC, ff.period_end DESC;
```

### Extending the Provider System

To add a new type of data provider:

1. **Determine the provider type**: Choose an existing type or add a new value to the `type` field (application validation may be needed)
2. **Register the provider**: Insert a record into the `data_providers` table
3. **Configure priority**: Set appropriate priority level relative to other providers
4. **Update ETL pipelines**: Ensure ingestion scripts properly set the `provider_id` when inserting data
5. **Consider source ID handling**: Determine if the provider uses unique identifiers that should be stored in the `source_id` field

### Best Practices

1. **Always attribute data**: Never insert data without specifying a `provider_id`
2. **Preserve original identifiers**: When available, store provider-specific IDs in the `source_id` column
3. **Maintain raw documents**: Whenever possible, preserve the original source files for audit and reproducibility
4. **Set appropriate priorities**: Reflect the reliability and timeliness of providers in priority settings
5. **Monitor provider health**: Use the `active` flag to enable/disable providers as needed
6. **Document provider specifics**: Maintain external documentation about each provider's data characteristics, update frequency, and known limitations

### Appendix: Common Provider Examples

#### Price Data Providers
- Exchange feeds (NASDAQ, NYSE, etc.)
- Consolidated tape providers (CTA, UTP)
- Financial data vendors (Bloomberg, Refinitiv, FactSet)
- Alternative data sources (IEX, Polygon.io, Alpha Vantage)
- Broker-dealers (various)

#### Fundamental Data Providers
- SEC EDGAR (primary source for U.S. public companies)
- Financial data aggregators (FactSet, Refinitiv, Bloomberg)
- Statistical agencies (Bureau of Economic Analysis, Census Bureau)
- Rating agencies (Moody's, S&P, Fitch) for credit fundamentals
- ESG data providers (MSCI, Sustainalytics)

#### Regulatory Data Providers
- SEC (EDGAR system)
- CFTC (for futures and swaps data)
- FINRA (for broker-dealer and market data)
- Federal Reserve (for banking and monetary data)
- International equivalents (FCA, ESMA, BaFin, etc.)

#### Alternative Data Providers
- Satellite imagery providers
- Credit card transaction aggregators
- Web scraping and sentiment analysis firms
- Supply chain and logistics data providers
- Patent and trademark data providers