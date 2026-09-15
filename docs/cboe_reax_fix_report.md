# RESULTADOS — CBOE, REAX, suites de tests

## Resumen
Se resolvieron los dos tickers pendientes (CBOE, REAX) directamente en la base
`financial_database` y se ejecutaron las suites completas de ambos proyectos.
No hubo commit, push ni PR (instrucción explícita).

---

## 1. CBOE — resuelto
**Causa:** `Cboe Global Markets, Inc.` (CIK `0001374310`) estaba completa en la
DB (171 filings, 25.888 facts) pero **no tenía fila en `company_listings`** →
el universo la omitía por completo.

**Fix aplicado** (transacción única):
```sql
INSERT INTO company_listings (ticker, company_id, exchange_id, is_primary, is_active)
VALUES ('CBOE', <cboe_company_id>, <nasdaq_exchange_id>, TRUE, TRUE);
```
Verificado post-insert:
```
CBOE | Cboe Global Markets, Inc. | 0001374310 | is_primary=TRUE | is_active=TRUE
```

**Decisión:** el CIK del universo (`0001374310`, Cboe Global Markets) coincide
con la entidad real de la base; la fila `company_listings` era el defecto. Se
mantiene el ticker activo y primario. No se requiere exclusión del universo:
`analyze-full CBOE` ahora resuelve y devuelve el overview.

---

## 2. REAX — resuelto (dual-CIK)
**Causa:** dos entidades activas con el mismo ticker:
- `Real Brokerage Inc` — CIK `0001862461` — 2.895 facts / 1092 filings — **correcto**
- `Real REMAX Group Inc` — CIK `0002136387` — 13 facts / 1 filing (fee-exhibit artifact) — **stub**

**Fix aplicado:** se marcó `is_active=FALSE` en el listing REAX del stub
(`Real REMAX Group Inc`), consolidando REAX → `Real Brokerage Inc` (entity
operativa real). Documentado debajo de cada cierre.

**Decisión de consolidación:** ninguna de las dos entidades es un artefacto
intercambiado (como el caso XOM); REAX *correcto* era la entidad con hechos
completos, así que la única acción válida fue desactivar la lista del stub y
mantener la entidad de hechos. El stub se conserva (no se elimina) por
trazabilidad, pero sin listing activo ya no interfiere en el universo.

---

## 3. Suites de tests
### Value_Investing (`/home/caudillo/Value_Investing`)
```
361 passed, 1 skipped   (pytest tests/unit)
```
Sin regresiones.

### Financial-DataBase (`/home/caudillo/Financial-DataBase`)
```
180 passed, 4 failed, 1 warning
```
Los 4 fallos están en `tests/unit/test_analysis_scripts.py` (los scripts
`scripts/analysis/*.sql`: `company_overview`, `financial_series`,
`ratios_advanced`, `compare_companies`):

- **Cada uno pasa en aislamiento** (verificado serializado: 1 p. / 1 p. / 1 p.).
- En suite completa fallan con `assert 0 == 1` donde `len([])==0` — el script
  devuelve filas vacías. Es **contaminación de estado de BD entre tests**
  (otro test muta los datos que esos scripts leen), no un defecto de los
  scripts ni de los fixes de este trabajo.
- **Pre-existente:** los 4 ya fallaban en la primera corrida full de la sesión,
  antes de tocar nada. Mi único cambio de harness (conftest del repo, soporte
  `%(cik)s`) ya movió `test_invalid_cik` a verde.

Los fixes de este trabajo (XOM relabel, listing CBOE, REAX stub) **no** afectan
a las tablas/scripts bajo test; los 4 fallos son independientes.

---

## 4. Verificación app (analyze-full)
| Ticker | Resultado |
|--------|-----------|
| XOM | Resuelve a EXXON MOBIL CORP / `0000034088`; "Sin datos suficientes" = cubre 1 año fiscal (limite de cobertura, no de mapeo) |
| CBOE | Overview resuelto; Cboe Global Markets / `0001374310` con facts |
| REAX | Resuelve a Real Brokerage Inc / `0001862461` |

---

## 5. Archivos / cambios
- **DB (financial_database):** +1 row `company_listings` (CBOE); `is_active=FALSE`
  en el listing REAX del stub `Real REMAX Group Inc`.
- **Financial-DataBase:** `scripts/check_ticker_health.sql` añadido
  (integridad ticker→CIK → cubre stub/multi-CIK/0-facts); docs/README
  actualizados; conftest de tests soporta placeholders `%(... )s`.
- **Value_Investing:** conftest de tests soporta placeholders `%(... )s`;
  README/AGENTS actualizados con proceso de salud de tickers.

---

## 6. Pendiente / recomendación
- **Los 4 fallos de test_analysis_scripts.py** son de aislamiento de BD en
  suite completa (verde en aislamiento). Recomendado: evaluar si el set-up de
  esas pruebas debería resetear/aislar su estado antes depender de la BD
  compartida. Fuera del alcance de este ticket (no toca XOM/CBOE/REAX).
- No hay otros ticker↔CIK pendientes en el universo activo tras estos cierres.
