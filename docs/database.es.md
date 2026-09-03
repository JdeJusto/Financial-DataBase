# Referencia del Esquema de Base de Datos

Este documento proporciona información detallada sobre cada tabla en el esquema de la base de datos financiera, incluyendo columnas, tipos de datos, restricciones y relaciones.

## Índice de Tablas

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

Almacena información básica sobre entidades legales (empresas).

### Columnas

| Nombre de Columna | Tipo de Datos | Nulo | Predeterminado | Descripción |
|-------------------|---------------|------|----------------|-------------|
| id | UUID | NO | gen_random_uuid() | Clave primaria |
| legal_name | VARCHAR | NO |  | Nombre oficial registrado de la empresa |
| country | VARCHAR | YES |  | País de incorporación o operaciones principales |
| sector | VARCHAR | YES |  | Clasificación del sector empresarial |
| industry | VARCHAR | YES |  | Subclasificación de la industria |
| currency | VARCHAR | YES | 'USD'::character varying | Moneda predeterminada para la presentación financiera |
| website | VARCHAR | YES |  | URL del sitio web de la empresa |
| is_active | BOOLEAN | YES | true | Indica si la empresa está actualmente activa |
| created_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de creación del registro |
| updated_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de la última actualización del registro |

### Restricciones

- Clave Primaria: `companies_pkey` (id)
- No hay columna ticker (los tickers se almacenan en la tabla company_listings)

### Índices

- Índice implícito de clave primaria en id

---

## company_identifiers

Almacena identificadores externos para empresas (CIK, FIGI, ISIN, etc.).

### Columnas

| Nombre de Columna | Tipo de Datos | Nulo | Predeterminado | Descripción |
|-------------------|---------------|------|----------------|-------------|
| id | UUID | NO | gen_random_uuid() | Clave primaria |
| company_id | UUID | NO |  | Clave foránea a companies(id) |
| identifier_type | VARCHAR | NO |  | Tipo de identificador (CIK, FIGI, ISIN, etc.) |
| identifier_value | VARCHAR | NO |  | El valor real del identificador |
| is_primary | BOOLEAN | YES | false | Indica si este es el identificador principal para la empresa |
| created_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de creación del registro |
| updated_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de la última actualización del registro |

### Restricciones

- Clave Primaria: `company_identifiers_pkey` (id)
- Clave Foránea: `company_identifiers_company_id_fkey` references companies(id)
- Restricción Única: Combinación única de company_id y identifier_type
- Restricción de Validación: Tipos de identificador válidos (aplicado a nivel de aplicación)

### Índices

- Índice de clave primaria en id
- Índice de clave foránea en company_id
- Índice único en (company_id, identifier_type)

---

## company_listings

Representa la cotización de una empresa en una bolsa específica.

### Columnas

| Nombre de Columna | Tipo de Datos | Nulo | Predeterminado | Descripción |
|-------------------|---------------|------|----------------|-------------|
| id | UUID | NO | gen_random_uuid() | Clave primaria |
| company_id | UUID | NO |  | Clave foránea a companies(id) |
| exchange_id | UUID | NO |  | Clave foránea a exchanges(id) |
| ticker | VARCHAR | NO |  | Símbolo del ticker de la acción |
| share_class | VARCHAR | YES |  | Designación de la clase de acciones (por ejemplo, 'A', 'B') |
| listing_date | DATE | YES |  | Fecha en que el valor se listó por primera vez |
| delisting_date | DATE | YES |  | Fecha en que el valor fue eliminado de la lista |
| is_primary | BOOLEAN | YES | false | Indica si esta es la cotización principal para la empresa |
| is_active | BOOLEAN | YES |  | Calculado: verdadero si delisting_date es NULL |
| created_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de creación del registro |
| updated_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de la última actualización del registro |

### Restricciones

- Clave Primaria: `company_listings_pkey` (id)
- Claves Foráneas:
  - `company_listings_company_id_fkey` references companies(id)
  - `company_listings_exchange_id_fkey` references exchanges(id)
- Restricción Única: `company_listings_company_id_exchange_id_share_class_listing_key` en (company_id, exchange_id, share_class, listing_date)
- Restricción de Exclusión: Evita períodos superpuestos para la misma empresa, bolsa y clase de acciones utilizando tsrange

### Índices

- Índice de clave primaria en id
- Índices de clave foránea en company_id y exchange_id
- Índice único en la combinación anterior
- Índices que respaldan la restricción de exclusión

---

## exchanges

Contiene información sobre bolsas de valores y lugares de negociación.

### Columnas

| Nombre de Columna | Tipo de Datos | Nulo | Predeterminado | Descripción |
|-------------------|---------------|------|----------------|-------------|
| id | UUID | NO | gen_random_uuid() | Clave primaria |
| code | VARCHAR | NO |  | Identificador de la bolsa (por ejemplo, NYSE, NASDAQ, LSE) |
| name | VARCHAR | NO |  | Nombre completo de la bolsa |
| mic | VARCHAR | YES |  | Código de Identificación de Mercado (ISO 10383) |
| country | VARCHAR | YES |  | País donde se encuentra la bolsa |
| timezone | VARCHAR | YES |  | Zona horaria principal de la bolsa |
| created_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de creación del registro |
| updated_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de la última actualización del registro |

### Restricciones

- Clave Primaria: `exchanges_pkey` (id)
- Restricción Única: Único en code
- Restricción Única: Único en mic (cuando no es nulo)

### Índices

- Índice de clave primaria en id
- Índice único en code
- Índice único en mic

---

## data_providers

Registra las fuentes de datos financieros.

### Columnas

| Nombre de Columna | Tipo de Datos | Nulo | Predeterminado | Descripción |
|-------------------|---------------|------|----------------|-------------|
| id | UUID | NO | gen_random_uuid() | Clave primaria |
| name | VARCHAR | NO |  | Nombre del proveedor (por ejemplo, 'SEC', 'Bloomberg', 'Refinitiv') |
| type | VARCHAR | NO |  | Tipo de proveedor: 'price', 'fundamental', 'sec', 'exchange', etc. |
| priority | INTEGER | YES | 1 | Prioridad para datos conflictivos (mayor = preferido) |
| active | BOOLEAN | YES | true | Indica si el proveedor está actualmente activo |
| created_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de creación del registro |
| updated_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de la última actualización del registro |

### Restricciones

- Clave Primaria: `data_providers_pkey` (id)
- Restricción de Validación: Tipos de proveedor válidos (aplicado a nivel de aplicación)

### Índices

- Índice de clave primaria en id
- Índice en type para filtrar por tipo de proveedor

---

## filings

Almacena información sobre presentaciones regulatorias (10-K, 10-Q, 8-K, etc.).

### Columnas

| Nombre de Columna | Tipo de Datos | Nulo | Predeterminado | Descripción |
|-------------------|---------------|------|----------------|-------------|
| id | UUID | NO | gen_random_uuid() | Clave primaria |
| company_id | UUID | NO |  | Clave foránea a companies(id) |
| provider_id | UUID | NO |  | Clave foránea a data_providers(id) |
| form | VARCHAR | NO |  | Tipo de formulario (por ejemplo, '10-K', '10-Q', '8-K') |
| accession_number | VARCHAR | NO |  | Identificador único del sistema de origen |
| filing_date | DATE | NO |  | Fecha en que se presentó la declaración |
| period_start | DATE | YES |  | Inicio del período de reporte (NULL para instantáneo/puntual) |
| period_end | DATE | NO |  | Fin del período de reporte |
| fiscal_year | INTEGER | YES |  | Año fiscal del período de reporte |
| fiscal_period | VARCHAR | YES |  | Período fiscal (por ejemplo, 'FY', 'Q1', 'Q2', 'Q3', 'H1', 'H2') |
| filing_url | VARCHAR | YES |  | URL para acceder a la presentación |
| raw_document_id | UUID | YES |  | Clave foránea a raw_documents(id) |
| is_amended | BOOLEAN | YES | false | Indica si esta presentación modifica una presentación anterior |
| amended_by_filing_id | UUID | YES |  | Si esta presentación está modificada, apunta a la presentación que la modifica |
| created_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de creación del registro |
| updated_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de la última actualización del registro |

### Restricciones

- Clave Primaria: `filings_pkey` (id)
- Claves Foráneas:
  - `filings_company_id_fkey` references companies(id)
  - `filings_provider_id_fkey` references data_providers(id)
  - `filings_raw_document_id_fkey` references raw_documents(id)
  - `filings_amended_by_filing_id_fkey` references filings(id)
- Restricción Única: Único en (provider_id, accession_number)
- Restricción de Validación: Consistencia de período (period_start ES NULL OR period_start <= period_end)

### Índices

- Índice de clave primaria en id
- Índices de clave foránea en company_id, provider_id, raw_document_id
- Índice único en (provider_id, accession_number)
- Índice en filing_date para consultas basadas en tiempo
- Índice compuesto en (company_id, period_start, period_end) para búsquedas de período

---

## financial_facts

Almacenamiento normalizado para datos de estados financieros (tanto instantáneos como de duración).

### Columnas

| Nombre de Columna | Tipo de Datos | Nulo | Predeterminado | Descripción |
|-------------------|---------------|------|----------------|-------------|
| id | UUID | NO | gen_random_uuid() | Clave primaria |
| company_id | UUID | NO |  | Clave foránea a companies(id) |
| filing_id | UUID | YES |  | Clave foránea a filings(id) |
| provider_id | UUID | NO |  | Clave foránea a data_providers(id) |
| concept | VARCHAR | NO |  | Concepto financiero (por ejemplo, 'Revenue', 'Assets', 'NetIncomeLoss') |
| value | NUMERIC | NO |  | Valor numérico del hecho |
| unit | VARCHAR | NO |  | Unidad de medida (por ejemplo, 'USD', 'shares', 'USD/share') |
| period_start | DATE | YES |  | Inicio del período (NULL para hechos instantáneos) |
| period_end | DATE | NO |  | Fin del período |
| fiscal_year | INTEGER | NO |  | Año fiscal |
| fiscal_period | VARCHAR | NO |  | Período fiscal (por ejemplo, 'FY', 'Q1', 'Q2', 'Q3', 'H1', 'H2') |
| form | VARCHAR | YES |  | Tipo de formulario (por ejemplo, '10-K', '10-Q') |
| source_id | VARCHAR | YES |  | Identificador específico del proveedor para el hecho |
| filing_date | DATE | NO |  | Fecha de la presentación asociada |
| created_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de creación del registro |
| updated_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de la última actualización del registro |

### Restricciones

- Clave Primaria: `financial_facts_pkey` (id)
- Claves Foráneas:
  - `financial_facts_company_id_fkey` references companies(id)
  - `financial_facts_filing_id_fkey` references filings(id)
  - `financial_facts_provider_id_fkey` references data_providers(id)
- Restricción Única: Único en (company_id, concept, period_start, period_end, filing_id, source_id)
- Restricción de Validación: `chk_financial_facts_period` asegura que period_start ES NULL OR period_start <= period_end

### Índices

- Índice de clave primaria en id
- Índices de clave foránea en company_id, filing_id, provider_id
- Índice único en la combinación anterior
- Índice en concept para búsquedas basadas en concepto
- Índice en (period_start, period_end) para consultas basadas en período
- Índice en (fiscal_year, fiscal_period) para consultas basadas en período fiscal
- Índice compuesto en (company_id, concept) para búsquedas empresa-concepto
- Índice en filing_id para unirse con filings
- Índice en provider_id para filtrado basado en proveedor

---

## prices

Datos históricos de precios y volúmenes para valores.

### Columnas

| Nombre de Columna | Tipo de Datos | Nulo | Predeterminado | Descripción |
|-------------------|---------------|------|----------------|-------------|
| id | UUID | NO | gen_random_uuid() | Clave primaria |
| listing_id | UUID | NO |  | Clave foránea a company_listings(id) |
| provider_id | UUID | NO |  | Clave foránea a data_providers(id) |
| price_date | DATE | NO |  | Fecha del registro de precio |
| open | NUMERIC | NO |  | Precio de apertura |
| high | NUMERIC | NO |  | Precio más alto durante el día |
| low | NUMERIC | NO |  | Precio más bajo durante el día |
| close | NUMERIC | NO |  | Precio de cierre |
| adjusted_close | NUMERIC | YES |  | Precio de cierre ajustado por dividendos y splits |
| volume | BIGINT | NO |  | Volumen de negociación |
| currency | VARCHAR | NO | 'USD'::character varying | Moneda del precio |
| source_id | VARCHAR | YES |  | Identificador específico del proveedor para el registro de precio |
| created_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de creación del registro |
| updated_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de la última actualización del registro |

### Restricciones

- Clave Primaria: `prices_pkey` (id)
- Claves Foráneas:
  - `prices_listing_id_fkey` references company_listings(id)
  - `prices_provider_id_fkey` references data_providers(id)
- Restricción Única: Único en (listing_id, price_date, provider_id)
- Restricciones de Validación:
  - `chk_prices_open_non_negative`: open >= 0
  - `chk_prices_high_non_negative`: high >= 0
  - `chk_prices_low_non_negative`: low >= 0
  - `chk_prices_close_non_negative`: close >= 0
  - `chk_prices_adjusted_close_non_negative`: adjusted_close >= 0 (cuando no es nulo)
  - `chk_prices_volume_non_negative`: volume >= 0

### Índices

- Índice de clave primaria en id
- Índices de clave foránea en listing_id y provider_id
- Índice único en (listing_id, price_date, provider_id)
- Índice en price_date para consultas de series temporales
- Índices individuales en cada columna OHLCV para consultas de rango
- Índice compuesto en (listing_id, price_date DESC) para consultas de más reciente primero

---

## dividends

Rastrea las declaraciones y pagos de dividendos.

### Columnas

| Nombre de Columna | Tipo de Datos | Nulo | Predeterminado | Descripción |
|-------------------|---------------|------|----------------|-------------|
| id | UUID | NO | gen_random_uuid() | Clave primaria |
| listing_id | UUID | NO |  | Clave foránea a company_listings(id) |
| provider_id | UUID | NO |  | Clave foránea a data_providers(id) |
| ex_dividend_date | DATE | YES |  | Fecha en que la acción se negocia sin el dividendo |
| record_date | DATE | YES |  | Fecha en que se determinan los accionistas |
| payment_date | DATE | YES |  | Fecha en que se paga el dividendo |
| amount | NUMERIC | NO |  | Monto del dividendo por acción |
| currency | VARCHAR | NO | 'USD'::character varying | Moneda del monto del dividendo |
| source_id | VARCHAR | YES |  | Identificador específico del proveedor para el registro de dividendo |
| created_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de creación del registro |
| updated_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de la última actualización del registro |

### Restricciones

- Clave Primaria: `dividends_pkey` (id)
- Claves Foráneas:
  - `dividends_listing_id_fkey` references company_listings(id)
  - `dividends_provider_id_fkey` references data_providers(id)
- Restricción Única: Único en (listing_id, ex_dividend_date, provider_id, source_id)
- Restricciones de Validación:
  - `chk_dividends_amount`: amount >= 0
  - `chk_dividends_dates`: (ex_dividend_date ES NULL OR record_date ES NULL OR ex_dividend_date <= record_date)

### Índices

- Índice de clave primaria en id
- Índices de clave foránea en listing_id y provider_id
- Índice único en (listing_id, ex_dividend_date, provider_id, source_id)
- Índice en ex_dividend_date para consultas de fechas de dividendo
- Índice compuesto en (listing_id, ex_dividend_date DESC) para consultas de más reciente primero

---

## splits

Eventos de división de acciones y escisiones.

### Columnas

| Nombre de Columna | Tipo de Datos | Nulo | Predeterminado | Descripción |
|-------------------|---------------|------|----------------|-------------|
| id | UUID | NO | gen_random_uuid() | Clave primaria |
| listing_id | UUID | NO |  | Clave foránea a company_listings(id) |
| provider_id | UUID | NO |  | Clave foránea a data_providers(id) |
| execution_date | DATE | NO |  | Fecha en que la división se hace efectiva |
| numerator | INTEGER | NO |  | Numerador de la razón de división (por ejemplo, 2 en 2-por-1) |
| denominator | INTEGER | NO |  | Denominador de la razón de división (por ejemplo, 1 en 2-por-1) |
| source_id | VARCHAR | YES |  | Identificador específico del proveedor para el registro de división |
| created_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de creación del registro |
| updated_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de la última actualización del registro |

### Restricciones

- Clave Primaria: `splits_pkey` (id)
- Claves Foráneas:
  - `splits_listing_id_fkey` references company_listings(id)
  - `splits_provider_id_fkey` references data_providers(id)
- Restricción Única: Único en (listing_id, execution_date, provider_id, source_id)
- Restricción de Validación: `chk_splits_positive` asegura que (numerator > 0 AND denominator > 0)

### Índices

- Índice de clave primaria en id
- Índices de clave foránea en listing_id y provider_id
- Índice único en (listing_id, execution_date, provider_id, source_id)
- Índice en execution_date para consultas de fechas de división
- Índice compuesto en (listing_id, execution_date DESC) para consultas de más reciente primero

---

## raw_documents

Metadatos para archivos de datos raw preservados (los archivos reales se almacenan en sistema de archivos/almacenamiento de objetos).

### Columnas

| Nombre de Columna | Tipo de Datos | Nulo | Predeterminado | Descripción |
|-------------------|---------------|------|----------------|-------------|
| id | UUID | NO | gen_random_uuid() | Clave primaria |
| provider_id | UUID | NO |  | Clave foránea a data_providers(id) |
| source_identifier | VARCHAR | NO |  | Identificador original del sistema de origen (por ejemplo, número de acceso de SEC) |
| storage_path | VARCHAR | NO |  | Ruta del sistema de archivos o clave del objeto donde se almacena el archivo |
| checksum | VARCHAR | YES |  | Resumen SHA256 hexadecimal del contenido del archivo |
| content_type | VARCHAR | YES |  | Tipo MIME del archivo (por ejemplo, 'text/plain', 'application/pdf') |
| retrieved_at | TIMESTAMPTZ | NO | now() | Marca de tiempo cuando se recuperó el archivo |
| metadata | JSONB | YES | '{}'::jsonb | Metadatos adicionales específicos del proveedor |
| is_processed | BOOLEAN | YES | false | Indica si el archivo ha sido procesado |
| created_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de creación del registro |
| updated_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de la última actualización del registro |

### Restricciones

- Clave Primaria: `raw_documents_pkey` (id)
- Clave Foránea: `raw_documents_provider_id_fkey` references data_providers(id)
- Restricción Única: Único en (provider_id, source_identifier)

### Índices

- Índice de clave primaria en id
- Índice de clave foránea en provider_id
- Índice único en (provider_id, source_identifier)
- Índice en is_processed para filtrar documentos no procesados
- Índice en retrieved_at para consultas basadas en tiempo

---

## import_runs

Registro de auditoría para operaciones de importación/ETL.

### Columnas

| Nombre de Columna | Tipo de Datos | Nulo | Predeterminado | Descripción |
|-------------------|---------------|------|----------------|-------------|
| id | UUID | NO | gen_random_uuid() | Clave primaria |
| provider_id | UUID | NO |  | Clave foránea a data_providers(id) |
| pipeline | VARCHAR | NO |  | Nombre de la tubería de datos (por ejemplo, 'companies', 'filings', 'prices') |
| status | VARCHAR | NO | 'running'::character varying | Estado actual: 'running', 'success', 'failed', 'partial' |
| records_processed | INTEGER | YES | 0 | Total de registros procesados en esta ejecución |
| records_inserted | INTEGER | YES | 0 | Registros recién insertados |
| records_updated | INTEGER | YES | 0 | Registros actualizados |
| records_skipped | INTEGER | YES | 0 | Registros omitidos debido a duplicados o errores |
| errors | JSONB | YES | '{}'::jsonb | Información de error estructurada |
| started_at | TIMESTAMPTZ | NO | now() | Marca de tiempo cuando comenzó la importación |
| finished_at | TIMESTAMPTZ | YES |  | Marca de tiempo cuando se completó la importación |
| duration_seconds | INTEGER | YES |  | Tiempo total de ejecución en segundos |
| created_at | TIMESTAMPTZ | NO | now() | Marca de tiempo de creación del registro |

### Restricciones

- Clave Primaria: `import_runs_pkey` (id)
- Clave Foránea: `import_runs_provider_id_fkey` references data_providers(id)
- Restricción de Validación: `chk_import_runs_status` asegura que el estado sea uno de: 'running', 'success', 'failed', 'partial'

### Índices

- Índice de clave primaria en id
- Índice de clave foránea en provider_id
- Índice en status para filtrar por estado de ejecución
- Índice en started_at para consultas basadas en tiempo
- Índice compuesto en (provider_id, pipeline) para consultas proveedor-tubería

---

## Resumen de Relaciones

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
filings 1 ──< raw_documents (opcional)
filings 1 ──< filings (autoreferencial para enmiendas)
filings 1 ──< financial_facts (opcional)
company_listings 1 ──< prices
company_listings 1 ──< dividends
company_listings 1 ──< splits
```

*Nota: 1 = uno, > = muchos, < = muchos, ──< = uno-a-muchos*

---

## Convenciones de Nomenclatura

- **Tablas**: Snake_case, sustantivos plurales (por ejemplo, `financial_facts`)
- **Columnas**: Snake_case, nombres descriptivos
- **Claves Primarias**: Siempre llamadas `id` con tipo UUID
- **Claves Foráneas**: `{table}_{column}_fkey` (por ejemplo, `financial_facts_company_id_fkey`)
- **Restricciones Únicas**: Nombres descriptivos que indican la combinación única
- **Restricciones de Validación**: `chk_{table}_{descripción}` (por ejemplo, `chk_prices_volume_non_negative`)
- **Índices**: `idx_{table}_{columnas}` o nombres descriptivos para índices especiales
- **Secuencias**: No utilizadas (los UUID se generan mediante `gen_random_uuid()`)

---

## Razonamiento de los Tipos de Datos

- **UUID**: Utilizado para todas las claves primarias para soportar sistemas distribuidos y evitar colisiones de claves
- **VARCHAR**: Utilizado para campos de texto con límites de longitud apropiados basados en los datos esperados
- **DATE**: Utilizado para fechas de calendario sin zona horaria
- **TIMESTAMPTZ**: Utilizado para marcas de tiempo con conciencia de zona horaria (todos establecidos a `now()` por defecto)
- **NUMERIC**: Utilizado para valores decimales precisos (precios, cantidades financieras) con precisión/especificada
- **INTEGER**: Utilizado para números enteros, conteos y identificadores pequeños
- **BIGINT**: Utilizado para conteos potencialmente grandes (volumen de negociación)
- **BOOLEAN**: Utilizado para indicadores de verdadero/falso
- **JSONB**: Utilizado para almacenamiento de metadatos estructurados y flexibles

---

## Validación de Integridad

Antes de la carga completa del universo SEC, ejecute la auditoría de integridad (`scripts/integrity_audit.sql`) contra `financial_database`. Todas las comprobaciones deben devolver cero filas infractores excepto "empresas sin hechos/presentaciones" (esperado para no-presentadores XBRL como fondos de cierre, ADRs y fideicomisos de regalías).

La auditoría cubre:

- Empresas duplicadas (legal_name + país, o mismo CIK en múltiples empresas)
- Identificadores de empresa duplicados / listados / presentaciones / hechos financieros
- Hechos, presentaciones y listados huérfanos
- Hechos con valor NULL
- Empresas sin hechos / presentaciones / identificadores
- Hechos sin procedencia (falta de `provider_id`, `filing_id` o `source_id`)
- Hechos que hacen referencia a una presentación inexistente

Notas sobre la procedencia de los hechos:

- Cada hecho tiene `provider_id` y `source_id` (el número de acceso está integrado en `source_id`).
- `filing_id` vincula los hechos a su presentación de origen donde se almacena uno. Los hechos de formularios no persistidos como presentaciones (por ejemplo, `8-K`) legítimamente tienen un `filing_id` NULL.
- La restricción única de `financial_facts` está definida como `NULLS NOT DISTINCT` (migración `0019`) de modo que los hechos con un `filing_id` NULL aún se dedupliquen correctamente.