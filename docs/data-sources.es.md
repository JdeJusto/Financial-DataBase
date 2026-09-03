# Fuentes de Datos y Proveedores

Este documento describe el modelo de fuente de datos utilizado en la base de datos financiera, incluidos los tipos de proveedor, identificación de fuentes y seguimiento de procedencia de datos.

## Modelo de Proveedor

La base de datos financiera usa un enfoque centrado en proveedor para rastrear el origen y confiabilidad de los datos financieros. Cada punto de datos del sistema puede rastrearse hasta su proveedor origen, enabling lineage de datos, resolución de conflictos y evaluación de calidad.

### Atributos del Proveedor

Cada proveedor de datos en el sistema tiene los siguientes atributos:

- **id**: Primary key UUID
- **name**: Nombre legible del proveedor (p. ej., "SEC EDGAR", "Bloomberg", "Refinitiv")
- **type**: Tipo categórico del proveedor que determina qué tipo de datos provee el proveedor
- **priority**: Entero usado para resolver conflictos cuando múltiples proveedores suministran el mismo punto de datos (gana el de mayor prioridad)
- **active**: Bandera booleana que indica si el proveedor está activo actualmente
- **created_at/updated_at**: Auditor timestamps

### Tipos de Proveedor

El sistema define varios tipos estándar, aunque el esquema permite extensión:

| Tipo de Proveedor | Descripción | Datos Típicos Suministrados |
|-------------------|-------------|----------------------------|
| `price` | Proveedores de datos de mercado | Precios de acciones, volúmenes, datos OHLCV |
| `fundamental` | Proveedores de estados financieros | Balance, estado de resultados, flujo de efectivo |
| `sec` | Comisión de Valores y Exchange de EE.UU. | Presentaciones regulatorias (10-K, 10-Q, 8-K, etc.), metadatos de empresas |
| `exchange` | Bolsas de valores | Datos de listing oficial, estado de trading, acciones corporativas |
| `registry` | Registros de identificadores | Mapeos FIGI, ISIN, CUSIP, LEI |
| `analyst` | Analistas financieros | Estimaciones, ratings, precios objetivo |
| `economic` | Proveedores de datos económicos | Indicadores macroeconómicos, tasas de interés, datos de PIB |
| `news` | Agregadores de noticias | Comunicados de prensa, artículos de noticias, datos de sentimiento |
| `rating` | Agencias de calificación | Ratings de crédito, evaluaciones de riesgo |
| `custom` | Fuentes definidas por usuario | Datos propietarios, cálculos internos, entradas manuales |

### Identificación de Origen

Cada proveedor puede usar diferentes esquemas de identificación para las mismas entidades. La base de datos acomoda esto a través:

1. **source IDs específicos del proveedor**: Muchas tablas incluyen una columna opcional `source_id` VARCHAR que almacena el identificador propio del proveedor para un registro
2. **Tablas cross-reference**: La tabla `company_identifiers` mantiene mapeos entre diferentes sistemas de identificación
3. **Preservación de documentos raw**: La tabla `raw_documents` preserva los identificadores originales de los sistemas origen

### Seguimiento de Procedencia

Cada tabla major del sistema incluye seguimiento de procedencia:

1. **Atribución de Proveedor**: Todas las tablas core de datos (`financial_facts`, `prices`, `dividends`, `splits`, `filings`) incluyen un `provider_id` foreign key
2. **Atribución de Presentaciones**: Hechos financieros pueden enlazarse a su fuente presentación vía el `filing_id` foreign key
3. **Enlaces de Documentos Raw**: Las presentaciones pueden referenciar opcionalmente el documento original vía `raw_document_id`
4. **Registro de Auditoría de Importación**: La tabla `import_runs` registra cuándo y cómo se cargaron los datos al sistema

### Resolución de Conflictos

Cuando múltiples proveedores proveen datos contradictorios para la misma entidad (p. ej., diferentes precios para el mismo valor el mismo día), el sistema usa:

1. **Provider Priority**: Cada proveedor tiene un nivel de prioridad; los datos de prioridad más alta ganan en conflictos
2. **Timestamp Preference**: Para proveedores de misma prioridad, los datos más recientes pueden preferirse
3. **Source Tracking**: Todos los valores contradictorios se preservan en la base de datos con procedencia completa, permitiendo a las aplicaciones implementar lógica personalizada de resolución de conflictos

### Detalles del Proveedor SEC EDGAR

El proveedor SEC EDGAR es una implementación de primera clase con pipeline de ingestion completo.

#### Registro del Proveedor SEC

```sql
INSERT INTO data_providers (name, type, display_name, base_url, rate_limit_per_second, is_active)
VALUES ('SEC EDGAR', 'sec', 'SEC EDGAR', 'https://www.sec.gov', 10.0, TRUE)
ON CONFLICT (name) DO NOTHING;
```

La migración `0015_sec_provider_seed.sql` siembra este proveedor y exchanges SEC comunes.

#### Fuentes de Datos SEC

| Endpoint | Data | Tablas de Base de Datos |
|----------|------|------------------------|
| `/files/company_tickers_exchange.json` | Universo de empresas (CIK, nombre, ticker, exchange) | `companies`, `company_identifiers`, `company_listings`, `exchanges` |
| `/submissions/CIK##########.json` | Metadatos de presentaciones (accession, form, dates, periods) | `filings`, `raw_documents` |
| `/api/xbrl/companyfacts/CIK##########.json` | Hechos XBRL financieros (concepts, values, periods) | `financial_facts`, `raw_documents` |

#### Requisitos de Acceso SEC

- **User-Agent**: Requerido por SEC. Debe ser descriptivo con información de contacto.
  - Set via `SEC_USER_AGENT` environment variable
  - Formato: `"ApplicationName/Version ContactEmail"`
  - Ejemplo: `"financial-database/0.1 contact@example.com"`
- **Rate Limits**: SEC impone límites. El client implementa 10 req/s por defecto conservador.
- **HTTPS Only**: Todas las requests usan HTTPS.

#### Normalización de Datos SEC

| Campo SEC | Normalización | Almacenamiento en Base de Datos |
|-----------|---------------|------------------------------|
| CIK | Zero-padded a 10 dígitos | `company_identifiers.identifier_value` (type=CIK) |
| Accession Number | Dashes removed | `filings.accession_number`, `financial_facts.source_id` |
| Exchange | Mapped to internal code + MIC | `exchanges.code`, `exchanges.mic` |
| Units | Preserved exactly | `financial_facts.unit` |
| Namespace + Concept | Preserved as-is | `financial_facts.concept` (namespace en JSONB metadata) |
| Instant/Duration | `period_start` NULL para instant | `financial_facts.period_start` |
| Frame | Preserved if available | `financial_facts` metadata JSONB |
| Fiscal Period | Preserved (FY, Q1-Q4, H1, H2) | `financial_facts.fiscal_period` |

#### Manejo de Restatements

El mismo período económico puede aparecer en múltiples presentaciones (original, amendada, restatada). La base de datos permite coexistencia a través:

- Unique constraint on `(company_id, concept, period_start, period_end, filing_id, source_id)`
- `filing_id` enlaza a presentación específica (original vs amendada)
- `source_id` incluye accession + concepto + período para unicidad
- `is_amended` flag en filings rastrea cadena de amendaciones

#### Ingestión Bulk Histórica (Fase 3.5/3.6)

La característica de ingestión bulk SEC EDGAR habilita cargar el universo completo SEC EDGAR usando datasets bulk.

##### Archivos Bulk

| File | URL | Descripción | Tamaño |
|------|-----|-------------|--------|
| `companyfacts.zip` | `https://www.sec.gov/files/companyfacts.zip` | Todos los datos CompanyFacts XBRL | ~2GB compressed |
| `submissions.zip` | `https://www.sec.gov/files/submissions.zip` | Todas las presentaciones de filings | ~500MB compressed |
| `company_tickers_exchange.json` | `https://www.sec.gov/files/company_tickers_exchange.json` | Universo de empresas con tickers | ~5MB |

##### Comando CLI

```bash
# Ingestión bulk full (requiere confirmación)
financial-db sec bulk-ingest --confirm

# Test con compañías limitadas
financial-db sec bulk-ingest --limit 10 --data-dir ./data/raw/sec/bulk_extracted

# Download and process
financial-db sec bulk-ingest --download --limit 100 --confirm

# Reanudar desde checkpoint
financial-db sec bulk-ingest --checkpoint-file ./data/checkpoints/sec_bulk/companyfacts_checkpoint.json --confirm

# Dry run para validar setup
financial-db sec bulk-ingest --dry-run
```

##### Opciones

| Opción | Descripción |
|--------|-------------|
| `--data-dir PATH` | Directorio que contiene archivos bulk extraídos SEC |
| `--download` | Descargar los últimos bulk files de SEC antes de procesar |
| `--checkpoint-file PATH` | Path a checkpoint file para resumability |
| `--limit N` | Procesar solo las primeras N compañías (para testing) |
| `--dry-run` | Validar sin escribir a PostgreSQL |
| `--verbose` | Increase logging detail |
| `--confirm` | Confirm ingestión bulk full (required) |
| `--force` | Ignorar checkpoint previo y empezar desde cero |

##### Formato de Archivo Checkpoint

Los checkpoints se guardan como archivos JSON con la siguiente estructura:

```json
{
  "dataset": "companyfacts",
  "provider": "SEC EDGAR",
  "source_file": "/path/to/companyfacts.json",
  "source_file_checksum": "sha256_checksum_of_source_file",
  "last_processed_cik": "0000789019",
  "companies_processed": 1234,
  "facts_processed": 56789,
  "filings_processed": 456,
  "updated_at": "2024-01-15T10:30:00+00:00"
}
```

- **Atomic writes**: Checkpoints se escriben a un archivo temp y luego renamed para evitar corrupción
- **Checksum validation**: On resume, el source file checksum se compara; si cambió, se registra warning y processing starts fresh
- **Progress tracking**: Registra último CIK procesado, conteo companies/facts/filings

##### Resumability

Si el proceso se interrumpe o falla:

1. Re-run con el mismo `--checkpoint-file` path
2. El ingester carga el checkpoint y skips companies up to `last_processed_cik`
3. Processing resumes from the next company
4. Checkpoint se actualiza después de cada compañía completa

##### Idempotency

La ingestión bulk es totalmente idempotent:

- **Company-level**: Verifica si company existe por CIK antes de crear
- **Fact-level**: Usa unique constraint on `(company_id, concept, period_start, period_end, filing_id, source_id)` para skip duplicates
- **NULL filing_id**: El unique constraint es `NULLS NOT DISTINCT` (migración `0019`) así que facts cuyo `filing_id` es NULL still deduplicate correctamente
- **Re-running**: Ejecutar la misma ingestion twice produce zero new records
- **With checkpoint**: Ejecutar con un checkpoint completado resulta en zero processed companies

Los hechos se enlazan a su source filing vía `filing_id` donde un filing record existe (los filings se procesan antes que los hechos). Hechos de formas no persistidas como filings (p. ej. `8-K`) tienen un NULL `filing_id`; su accession number still está embedado en `source_id`.

##### Expected 404s

Companies that no file XBRL financial statements return HTTP 404 on the `companyfacts` endpoint. Esto es esperado y logged at INFO level (`expected_404: true`), no tratado como fallo. Ejemplos: closed-end funds (N-CSR filers), foreign ADRs, royalty trusts, y utility subsidiaries.

##### Output Summary

Al completarse, el comando imprime:

```
✅ Bulk ingestion complete:
   Companies processed: 1234
   Companies inserted: 1200
   Companies updated: 34
   Identifiers inserted: 1200
   Filings processed: 0
   Filings inserted: 0
   Filings skipped: 0
   Facts processed: 56789
   Facts inserted: 55000
   Facts skipped: 1789
   Facts validation errors: 0
   Errors encountered: 2
   Elapsed time: 3600.5s (60.0min)
```

##### Storage Requirements (validated)

- **Database**: ~170–200GB para el universo completo SEC (`financial_facts` dominate; ~10GB para 608 companies / 12.3M facts)
- **Raw files**: ~2.5GB para descargas bulk compressed
- **Extracted**: ~10–15GB para JSON uncompressed
- **Checkpoints**: <1MB

##### Performance Notes (validated)

- **Streaming parser**: Usa `ijson` para parsing memory-efficient de large JSON files
- **Batch commits**: Hechos se comprometen en batches de 500 filas por compañía
- **Measured rate**: ~5.0 s/company (network bound); ~14.5 hours para el full universe
- **Rate limiting**: 10 requests/sec max, conservative backoff on 429/5xx

##### Verificación de Completitud Histórica

Después de ingestión, verificar datos históricos con `scripts/verify_history.sql` (23 main companies; established filers reach back to fiscal year 2009).

```sql
-- Check earliest facts available
SELECT MIN(period_start) as earliest_period, COUNT(*) as fact_count
FROM financial_facts ff
JOIN companies c ON ff.company_id = c.id
JOIN company_identifiers ci ON c.id = ci.company_id
WHERE ci.identifier_type = 'CIK';

-- Verify specific company has historical data
SELECT concept, period_start, period_end, value
FROM financial_facts ff
JOIN companies c ON ff.company_id = c.id
JOIN company_identifiers ci ON c.id = ci.company_id
WHERE ci.identifier_value = '0000320193'  -- Apple
  AND ff.concept = 'Assets'
ORDER BY period_start;
```

#### Ingestión Incremental

- Raw documents tracked by `(provider_id, source_identifier)` with SHA-256 checksum
- Content changes preserve previous version con timestamp
- Import runs record processed/inserted/updated/skipped counts
- Re-running pipeline only processes new/changed data

### Configuraciones Typicas de Proveedor

#### Proveedores de Datos de Mercado

```sql
INSERT INTO data_providers (name, type, priority, active)
VALUES 
('NASDAQ', 'price', 100, true),
('NYSE', 'price', 100, true),
('Bloomberg', 'price', 80, true),
('Refinitiv', 'price', 80, true),
('IEX', 'price', 90, true);
```

#### Proveedores de Estados Financieros

```sql
INSERT INTO data_providers (name, type, priority, active)
VALUES 
('SEC', 'fundamental', 100, true),
('FactSet', 'fundamental', 80, true),
('S&P Capital IQ', 'fundamental', 80, true),
('Morningstar', 'fundamental', 70, true);
```

#### Proveedores de Datos Regulatorios

```sql
INSERT INTO data_providers (name, type, priority, active)
VALUES 
('SEC EDGAR', 'sec', 100, true),
('SEC', 'sec', 100, true);  -- Legacy alias if needed
```

#### Proveedores de Exchange

```sql
INSERT INTO data_providers (name, type, priority, active)
VALUES 
('NASDAQ', 'exchange', 100, true),
('NYSE', 'exchange', 100, true),
('LSE', 'exchange', 100, true),
('TSE', 'exchange', 100, true);
```

#### Flujo de Datos con Proveniencia

1. **Data Ingestion**: Proveedor externo envía datos a través de pipeline ETL
2. **Provider Validation**: Sistema verifica que proveedor existe y está active
3. **Raw Storage**: Archivo original se guarda en filesystem/storage object
4. **Metadata Recording**: Tabla `raw_documents` registra metadata sobre el archivo original
5. **Data Normalization**: Datos convertidos a formato estándar de base de datos
6. **Database Insertion**: Datos normalizados insertados con `provider_id` y opcional `source_id`
7. **Audit Recording**: Tabla `import_runs` registra estadísticas de operación de importación
8. **Conflict Detection**: Sistema identifica cualquier conflicto con datos existentes
9. **Resolution**: Conflicts resueltos según reglas de prioridad de proveedor (configurable)
10. **Availability**: Data becomes available para querying con procedencia completa

#### Consultando con Proveniencia

Ejemplos de cómo consultar datos con información de procedencia:

##### Obtener un financial fact con su proveedor

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

##### Obtener todos los precios para un valor con información de proveedor

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

##### Obtener una presentación con su documento fuente

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

##### Obtener hechos financieros SEC con provenance de filing

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

#### Extendiendo el Sistema de Proveedores

Para agregar un nuevo tipo de proveedor de datos:

1. **Determinar el tipo de proveedor**: Elegir un tipo existente o agregar un nuevo valor al campo `type` (puede ser necesario validación application)
2. **Registrar el proveedor**: Insertar un registro en la tabla `data_providers`
3. **Configurar prioridad**: Establecer nivel de prioridad apropiado relativo a otros proveedores
4. **Actualizar pipelines ETL**: Asegurar que scripts de ingestion correctamente set el `provider_id` al insertar datos
5. **Considerar handling de source ID**: Determinar si el proveedor usa identificadores únicos que deberían almacenarse en el campo `source_id`

#### Mejores Prácticas

1. **Siempre atribuir datos**: Nunca insertar datos sin especificar un `provider_id`
2. **Preservar identificadores originales**: Cuando estén disponibles, almacenar IDs específicos del proveedor en la columna `source_id`
3. **Mantener documentos raw**: Siempre que sea posible, preservar los archivos fuente original para auditoría y reproducibilidad
4. **Establecer prioridades apropiadas**: Reflejar la confiabilidad y puntualidad de proveedores en configuraciones de prioridad
5. **Monitorear salud del proveedor**: Usar el flag `active` para enable/disable proveedores según sea necesario
6. **Documentar specifics del proveedor**: Mantener documentación externa sobre cada proveedor, frecuencia de actualización y limitaciones conocidas

#### Anexo: Ejemplos Comunes de Proveedores

##### Proveedores de Datos de Mercado

- Exchange feeds (NASDAQ, NYSE, etc.)
- Consolidated tape providers (CTA, UTP)
- Financial data vendors (Bloomberg, Refinitiv, FactSet)
- Alternative data sources (IEX, Polygon.io, Alpha Vantage)
- Broker-dealers (various)

##### Proveedores de Datos Fundamentales

- SEC EDGAR (fuente primaria para empresas públicas EE.UU.)
- Financial data aggregators (FactSet, Refinitiv, Bloomberg)
- Statistical agencies (Bureau of Economic Analysis, Census Bureau)
- Rating agencies (Moody's, S&P, Fitch) para credit fundamentals
- ESG data providers (MSCI, Sustainalytics)

##### Proveedores de Datos Regulatorios

- SEC (EDGAR system)
- CFTC (para futures y swaps data)
- FINRA (para broker-dealer y market data)
- Federal Reserve (para banking y monetary data)
- International equivalents (FCA, ESMA, BaFin, etc.)

##### Proveedores de Datos Alternativos

- Satellite imagery providers
- Credit card transaction aggregators
- Web scraping y sentiment analysis firms
- Supply chain y logistics data providers
- Patent y trademark data providers