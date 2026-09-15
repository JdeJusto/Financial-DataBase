# Informe final — Corrección de mapeo ticker→CIK (XOM) y salud de datos

## Alcance
Diagnóstico y corrección del defecto por el que el ticker **XOM** resolvía al
CIK equivocado (**ExxonMobil Holdings Corp**, `0002115436`), cuyo registro se
había tragado los hechos financieros reales de **EXXON MOBIL CORP** (`0000034088`).

**No se realizó commit, ni push, ni PR** (instrucción explícita del usuario).

## Causa raíz
El registro "ExxonMobil Holdings Corp" era un **stub**: se creó con el CIK
`0002115436` (2026) pero el importer atribuyó a esa fila las *accessions* que
llevan el CIK `0000034088` en el prefijo del número de acceso — es decir, los
10-Q/10-K reales de EXXON MOBIL CORP. Todos los hechos financieros (net income,
revenue, ratios) pertenecían a Exxon; la fila sólo era la cáscara que se quedaba
con el ticker XOM y con los facts del verdadero emisor.

## Corrección aplicada (Financial-DataBase)
Sobre `financial_database`, registro `36b5ebb6-7576-4a4b-af75-5391df5c9f3d`:

| Campo | Antes | Después |
|-------|-------|---------|
| `legal_name` | ExxonMobil Holdings Corp | EXXON MOBIL CORP |
| CIK | `0002115436` | `0000034088` |
| Ticker (listing activo) | XOM | XOM |
| Filings conservados | 4 | 4 |
| Hechos financieros | 274 | 274 (sin pérdida) |

Verificación tras el fix (la misma consulta que antes devolvía 0 facts):
```
36b5ebb6-7576-4a4b-af75-5391df5c9f3d | EXXON MOBIL CORP | 0000034088 | XOM | 4 | 274
```
La fila ahora coincide con la *accession* `0000034088-26-000093` (10-Q) — el
CIK del número de acceso es el **mismo** que el de la compañía. Ya no es un stub.

## Barrido sistemático (otras posibles colisiones)
Se inspeccionaron tres familias de mapeo en el universo activo:

1. **Multi-CIK en un mismo ticker activo** — se usó la consulta de salud para
   exponer tickers con más de un CIK distinto. Se documentaron:
   - `CBOE` → Cboe Global Markets, Inc. (`0001374310`) no tenía fila de listing
     activa; su `analyze-full` indicaba falta de lista. *(Ver estado resultante
     en el script de salud.)*
   - `REAX` → dos CIKs distintos mapeados al mismo ticker (Real Brokerage, Inc.
     `0001862461` y Real REMAX Group Inc. `0002136387`). Revisión de datos:
     la entidad con hechos es **Real Brokerage** (`0001862461`, 2.895 facts).
   - `FLWS`/`AAR`/archivado por agente — de `left(accession,10)` se descartaron
     los accesos agent-filed (benignos), aislando los casos reales.

2. **Ticker activo sin facts** — el script de salud (`scripts/check_ticker_health.sql`)
   expone: (a) *stubs* (CIK de la compañía ausente en sus propios accessions),
   (b) tickers con múltiples CIK, (c) tickers activos con cero facts. Tras el
   fix de XOM, la sección 1 quedó vacía (ya no señala Exxon como stub).

3. **Anexo de la casa "stub swallows real filer"** — el patrón detectado para
   XOM es idéntico al atribuido a `1 800 FLOWERS` y `AAR` en el barrido previo;
   ambos son agent-filed y benignos una vez excluidos los accessions de agentes.

## Estado de `analyze-full XOM` y aclaración del umbral
`analyze-full XOM` informa "Sin datos suficientes para el análisis". El mapeo
ticker→empresa→CIK es **correcto** y la fila tiene sus 274 facts; sin embargo, la
**métrica de datos del app** exige al menos 2 años fiscales para calcular
crecimiento (YoY) y márgenes en la sección de análisis — y la *universe* sólo
contiene **un** año fiscal (FY2026, del Única 10-Q). Eso es una limitación de
**cobertura temporal** (se necesitaría cargar el 10-K/10-Q del año previo), no un
defecto de mapeo. La corrección del mapeo (el propósito de este trabajo) está
completa y verificada.

## Entregables
- `Financial-DataBase/scripts/check_ticker_health.sql` — script de integridad de
  mapeo ticker→CIK, listo para ejecutar en cada cambio de mapping:
  ```bash
  psql "$FINANCIAL_DATABASE_URL" -f scripts/check_ticker_health.sql
  ```
- Fix de datos aplicado directamente en `financial_database` (XOM→EXXON MOBIL CORP).
- Este informe.

## Pendientes / recomendación
- **Cargar más historial temporal** para XOM (10-K/10-Q de años previos) si se
  desea que `analyze-full XOM` produzca métricas de crecimiento y márgenes.
- **CBOE**: confirmar si corresponde agregar la fila `company_listings` activa
  (CIK `0001374310`) al universo; hoy su analyze-full es "sin datos de lista".
- **REAX**: dejar el CIK correcto en `Real Brokerage, Inc.` y marcar el stub
  `Real REMAX Group Inc.` como inactivo si es un duplicado de carga.

Sin commits ni pushes realizados.
