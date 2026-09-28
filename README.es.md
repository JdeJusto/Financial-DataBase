# Financial-DataBase

[English](README.md) · [Español](README.es.md)

Proyecto en Python y PostgreSQL para ingerir presentaciones regulatorias y hechos financieros de empresas, conservar su procedencia y consultarlos mediante una CLI y análisis SQL reutilizables.

> **Principio de diseño:** «Los tontos admiran la complejidad; los genios admiran la simpleza». El esquema, el flujo de datos y los comandos deben ser comprensibles; la procedencia se registra, no se oculta tras más capas.

## Qué ofrece

- Importación de identificadores de empresas, presentaciones SEC, submissions y hechos XBRL.
- Almacenamiento de hechos normalizados y precios diarios en PostgreSQL con procedencia por proveedor.
- Registro de ejecuciones, ingestión masiva reanudable y consultas SQL reutilizables.
- Interfaz de línea de comandos `financial-db`.

## Fuentes de datos y herramientas externas

| Fuente o herramienta | Uso |
| --- | --- |
| [SEC EDGAR](https://www.sec.gov/edgar) | Fuente principal de identificadores de empresas, presentaciones regulatorias, submissions y Company Facts XBRL. Las peticiones requieren un `SEC_USER_AGENT` descriptivo con datos de contacto válidos y deben respetar las políticas de acceso de SEC. |
| [Yahoo Finance](https://finance.yahoo.com/) mediante [`yfinance`](https://github.com/ranaroussi/yfinance) | Fuente actual de datos diarios OHLCV para `financial-db prices update`. A diferencia del servicio de precios bajo demanda de Value Investing, este proyecto **guarda los precios importados** en la tabla PostgreSQL `prices`. La cobertura, los retrasos y la disponibilidad dependen de Yahoo. |
| Stooq | Se conserva una implementación antigua del proveedor en el código; el comando actual `prices update` utiliza Yahoo Finance, no Stooq. |
| PostgreSQL | Base de datos necesaria para hechos normalizados, migraciones, procedencia y precios importados. Docker Compose ofrece un servicio local de desarrollo. |

El fichero versionado `data/company_tickers_full.json` es una instantánea de referencia SEC de empresas y tickers para resolver identificadores de forma reproducible. Son datos públicos de referencia, no sustituyen a las presentaciones SEC actuales. La licencia MIT de este proyecto cubre solo el código; los datos y marcas de terceros siguen sujetos a las condiciones de sus proveedores.

La pila principal usa Python, PostgreSQL, Psycopg 3, `aiohttp` e `ijson`;
la ingestión de precios de Yahoo también usa `yfinance` y pandas. La lista
completa de dependencias y extras opcionales está en `pyproject.toml`.

## Inicio rápido

Requisitos: Python 3.13+ y PostgreSQL 14+ (el archivo Compose usa PostgreSQL 18). El extra `dev` incluye las dependencias para precios de Yahoo.

```bash
git clone https://github.com/JdeJusto/Financial-DataBase.git
cd Financial-DataBase
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env
```

Edita `.env`: configura `DATABASE_URL` y sustituye el `SEC_USER_AGENT` de ejemplo por un nombre descriptivo de aplicación y un correo real de contacto. La CLI lee variables de entorno; carga el fichero en la shell antes de ejecutar comandos:

```bash
set -a
. ./.env
set +a

docker compose up -d postgres
python -m financial_database.cli migrate
financial-db sec sync 0000320193
financial-db prices update --limit 10
```

El último comando consulta Yahoo Finance en vivo y escribe los precios importados en la base de datos. Las credenciales predeterminadas de Compose son solo para desarrollo local; no las reutilices en un entorno publicado.

Para probar la ingestión masiva SEC con cautela, empieza con `financial-db sec bulk-ingest --dry-run` y una ejecución limitada. Una carga histórica completa puede requerir mucho almacenamiento y numerosas peticiones a SEC; consulta la [guía de carga completa](docs/runbook_full_load.md).

## Pruebas

```bash
python -m pytest tests/unit -q           # no necesita base de datos
```

Las pruebas de repositorios y SQL requieren una base PostgreSQL de pruebas
separada. Con la base de Compose en marcha, créala y aplica las migraciones una
vez:

```bash
docker compose up -d postgres
docker compose exec postgres createdb -U financial financial_database_test
DATABASE_URL=postgresql://financial:test@localhost:5432/financial_database_test \
  python -m financial_database.cli migrate
```

Después apunta los fixtures a esa base y ejecuta la suite de integración:

```bash
TEST_DB_NAME=financial_database_test \
TEST_DB_USER=financial TEST_DB_PASSWORD=test \
TEST_DB_HOST=localhost TEST_DB_PORT=5432 \
python -m pytest tests/integration -q
```

Las pruebas de análisis SQL se omiten si la base de test no contiene hechos SEC
de AAPL y MSFT. No apuntes los fixtures a una base con datos que quieras
conservar.

## Estructura del proyecto

```text
src/financial_database/ CLI, proveedores SEC y de precios, repositorios
db/migrations/          migraciones PostgreSQL ordenadas
scripts/analysis/        consultas SQL reutilizables
scripts/stress/          utilidades de pruebas de estrés
scripts/dev/             ayudas de desarrollo y mantenimiento
tests/unit/              pruebas aisladas
tests/integration/       pruebas de base de datos e ingestión
docs/                    guías, runbooks e informes históricos
```

## Documentación

- [Arquitectura](docs/architecture.es.md) · [Esquema de base de datos](docs/database.es.md)
- [Fuentes de datos](docs/data-sources.es.md) · [Guía de precios en inglés](docs/price_ingestion.md)
- [Scripts SQL de análisis](docs/analysis_scripts.md)
- [Actualizaciones diarias en inglés](docs/runbook_daily_update.md) · [Carga SEC completa en inglés](docs/runbook_full_load.md)
- [Contribuir](CONTRIBUTING.md) · [Seguridad](SECURITY.md) · [Código de conducta](CODE_OF_CONDUCT.md)

## Licencia

[MIT](LICENSE). La licencia cubre el código del proyecto, no los datos externos ni las condiciones de los proveedores.
