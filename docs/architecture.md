# Financial Database Architecture

## Visión General

La Base de Datos Financiera está diseñada como una base de datos PostgreSQL normalizada y extensible para almacenar y gestionar datos financieros de diversas fuentes. La arquitectura enfatiza la integridad de datos, el seguimiento de procedencia y la flexibilidad para acomodar diferentes tipos de datos financieros y frecuencias de informe.

## Principios de Diseño

1. **Normalización**: Los datos están estructurados para minimizar redundancia y dependencias
2. **Procedencia**: Cada punto de datos rastrea hasta su proveedor origen y documento original
3. **Extensibilidad**: nuevos tipos y proveedores de datos pueden agregarse sin cambios de esquema
4. **Auditabilidad**: Historial completo de importación y rastreo de línea de datos
5. **Rendimiento**: Índices estratégicos para patrones de consulta comunes

## Componentes Core

### 1. Datos Maestro de Empresas y Valores

- **companies**: Entidad core que representa entidades legales
- **company_identifiers**: Identificadores externos (CIK, FIGI, ISIN, etc.)
- **exchanges**: Bolsas de valores y venues de trading
- **company_listings**: Tabla junction que vincula empresas a exchanges con información de ticker

### 2. Capa de Proveniencia de Datos

- **data_providers**: Fuentes de datos financieros (SEC, Bloomberg, Reuters, etc.)
- Registra el tipo de proveedor (price, fundamental, sec, etc.) para enrutamiento apropiado

### 3. Almacenamiento de Datos Financieros

#### Datos en Serie Temporal

- **prices**: Datos OHLCV con atribución de proveedor
- **dividends**: Déclaraciones y pagos de dividendos
- **splits**: Eventos de división de acciones y desmembramientos

#### Datos de Estados Financieros

- **financial_facts**: Elementos de estados financieros normalizados
  - Compatible tanto hechos instantáneas (balance) como duration (estado de resultados)
  - Manejo de período con fecha start nullable para hechos instantáneas
  - Atribución completa de concepto, unidad y fuente

#### Datos de Eventos

- **filings**: Presentaciones regulatorias (10-K, 10-Q, 8-K, etc.)
- Vincula a documentos fuente y empresas

### 4. Preservación de Datos Raw

- **raw_documents**: Metadatos de archivos fuente originales
  - Archivos reales almacenados en filesystem/storage object
  - La base de datos solo almacena metadatos, checksums y rutas
  - Permite reproducibilidad y rastreo de auditoría

### 5. Infraestructura de Importación y Auditoría

- **import_runs**: Registro de auditoría ETL/import
  - Rastrea ejecución de pipelines, estados éxito/fallo
  - Registra procesados, insertados, actualizados y skipped
  - Colección de errores e información de tiempo

### 6. Arquitectura del Proveedor SEC EDGAR

El proveedor SEC implementa un pipeline de ingestion de producción siguiendo la abstracción de proveedor:

```
SEC EDGAR
    ↓
Almacenamiento Raw (filesystem)
    ↓
Parser (XBRL/JSON → modelos de dominio)
    ↓
Validación (reglas de negocio, constraints)
    ↓
Normalización (CIK, accession, exchange, units)
    ↓
Repositorio (upserts idempotent)
    ↓
PostgreSQL
```

#### Aislamiento del Proveedor

- **src/financial_database/providers/sec/** - Toda la lógica específica SEC aislada
- **src/financial_database/providers/base.py** - Clases base abstractas
- Los repositorios de base de datos no conocen detalles HTTP de SEC
- El cliente SEC no contiene lógica de negocio SQL

#### Cliente SEC (`client.py`)

- HTTPS solo con User-Agent explícito (requerido por SEC)
- Timeouts configurables, reintentos con backoff exponencial
- Respeta cabeceras HTTP 429 y Retry-After
- Rate limiting conservador (10 req/s por defecto)
- Registro estructurado sin secretos
- Almacenamiento de respuestas raw con checksums SHA-256

#### Modelos SEC (`models.py`)

- `SECCompany` - Universo de empresas desde reference tickers
- `SECSubmissions` / `SECFiling` - Metadatos de presentaciones (10-K, 10-Q, 8-K, 20-F, 40-F, 6-K)
- `SECCompanyFacts` / `SECCompanyFact` / `SECCompanyFactValue` - Hechos XBRL parseados
- Normalización de CIK (formato canonical de 10 dígitos con relleno a cero)
- Normalización de accession number (dashes removidos)
- Mapping de exchanges (nombres SEC → códigos internos con MIC)

#### Parser SEC (`parser.py`)

- Normaliza datos SEC a modelos de dominio (`ParsedCompany`, `ParsedFiling`, `ParsedFinancialFact`)
- Preserva identidad de namespace XBRL + concepto (sin colapsar)
- Preserva unidades SEC originales (USD, shares, USD/shares, pure, etc.)
- Distingue correctamente hechos instantáneas vs duration
- Preserva información de frame (CY2023, CY2023Q1, etc.)
- Preserva metadatos de period fiscal (FY, Q1, Q2, Q3, Q4)
- Validación antes de inserción

#### Importador SEC (`importer.py`)

- Operaciones idempotent usando constraints únicas de base de datos
- Seguimiento de documentos raw con checksums (preserva historia en caso de cambio de contenido)
- Registro de auditoría de importación para cada ejecución del pipeline
- Soporte para restatement: hechos originales + hechos amended coexisten vía filing_id/source_id
- Incremental ingestion vía raw_documents y source identifiers
- Manejo de errores con recovery por registro donde sea seguro

## Decisiones Arquitectónicas Clave

### Primary Keys UUID

- Todas las tablas usan UUIDs como primary keys para compatibilidad con sistemas distribuidos
- Previene colisiones de keys al fusionar datos de múltiples fuentes
- Generados usando `gen_random_uuid()` para rendimiento

### Atribución de Proveedor

- Cada tabla major incluye un `provider_id` foreign key
- Permite rastrear línea de datos y resolver conflictos entre proveedores
- Source IDs específicos del proveedor mantienen donde sea aplicable

### Manejo Temporal

- Hechos financieros soportan tanto datos instantáneos como periodo a través de `period_start` nullable
- Constraints validan validez temporal (`period_start <= period_end` o `period_start IS NULL`)
- Import runs rastrean tiempo de ejecución para monitoreo de desempeño y tracking SLA

### Integrity Based on Constraints

- Check constraints enforcen reglas de negocio a nivel de base de datos:
  - Precios y volúmenes no negativos
  - Relaciones de fecha válidas
  - Validación de enumeración de status
  - Números/denominadores positivos para splits

### Estrategia de Índices

- Primary key indexes en todas las columnas UUID
- Foreign key indexes para performance de joins
- Composite indexes para patrones de consulta comunes:
  - Company+concept+period para retrieval de financial facts
  - Listing+date para lookups de price/volume
  - Provider-based indexes para aislamiento de datos source
  - Índices de status y timing para queries de import audit

### Patrones de Extensibilidad

- JSONB fields para almacenamiento flexible de atributos
- VARCHAR source IDs para identifiers específicos del proveedor
- El diseño permite agregar nuevos tipos de datos siguiendo patrones existentes
- Sistema de migración soporta evolución de esquema

## Flujo de Datos

1. **Ingestion**: Proveedores externos de datos submiten datos a través de pipelines ETL
2. **Staging**: Archivos raw preservados en filesystem/storage object con metadata de base de datos
3. **Processing**: Datos validados, normalizados e insertados en tablas apropiadas
4. **Audit**: Import runs registran estadísticas de procesamiento y cualquier error
5. **Consumption**: Aplicaciones consultan datos normalizados con procedencia completa

### Flujo de Datos Específico SEC

1. **Universe**: Fetch company tickers exchange reference → upsert companies, identifiers, listings, exchanges
2. **Submissions**: Para cada CIK, fetch submissions metadata → upsert filings con enlaces raw_document
3. **CompanyFacts**: Para cada CIK, fetch XBRL CompanyFacts → parse facts → validate → insert financial_facts
4. **Provenance**: Cada paso crea raw_documents entries y import_runs records

## Consideraciones de Seguridad

- Se recomienda control de acceso basado en roles para deployment en producción
- Encriptación SSL/TLS de conexiones
- Backups regulares y recovery punto-a-tiempo
- Registro de auditoría preserva todos los cambios para compliance
- SEC_USER_Agent from environment (never hardcoded, never logged)
- Respuestas SEC raw nunca commiteadas a Git

## Consideraciones de Escalabilidad

- Estrategia de particionamiento puede implementarse para tablas time-series grandes
- Read replicas para distribución de queries
- Connection pooling para acceso concurrente
- Estrategia de archivado para datos históricos más allá del período de retención activo
- Ingestion SEC es intencionalmente conservadora (rate limited, sequential)