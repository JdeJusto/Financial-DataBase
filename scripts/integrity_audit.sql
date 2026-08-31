-- Database Integrity Audit
-- Run against financial_database before the full SEC universe load.
--
-- Each section prints zero or more offending rows. All sections except
-- "companies with no facts/filings" should return zero rows.

\set ON_ERROR_STOP off

\echo '=== 1a. Duplicate companies by (legal_name, country) ==='
SELECT legal_name, country, count(*) AS n
FROM companies
GROUP BY legal_name, country
HAVING count(*) > 1;

\echo '=== 1b. Duplicate companies by CIK (same CIK on multiple companies) ==='
SELECT identifier_value AS cik, count(DISTINCT company_id) AS n_companies
FROM company_identifiers
WHERE identifier_type = 'CIK'
GROUP BY identifier_value
HAVING count(DISTINCT company_id) > 1;

\echo '=== 2. Duplicate company identifiers (company_id, type, value) ==='
SELECT company_id, identifier_type, identifier_value, count(*) AS n
FROM company_identifiers
GROUP BY company_id, identifier_type, identifier_value
HAVING count(*) > 1;

\echo '=== 3. Duplicate listings (company_id, exchange_id, ticker, active) ==='
SELECT company_id, exchange_id, ticker, count(*) AS n
FROM company_listings
WHERE is_active = TRUE
GROUP BY company_id, exchange_id, ticker
HAVING count(*) > 1;

\echo '=== 4. Duplicate filings (provider_id, accession_number) ==='
SELECT provider_id, accession_number, count(*) AS n
FROM filings
GROUP BY provider_id, accession_number
HAVING count(*) > 1;

\echo '=== 5. Duplicate financial facts (company_id, concept, period, filing, source) ==='
SELECT company_id, concept, period_start, period_end, filing_id, source_id, count(*) AS n
FROM financial_facts
GROUP BY company_id, concept, period_start, period_end, filing_id, source_id
HAVING count(*) > 1;

\echo '=== 6. Orphaned facts (company_id missing) ==='
SELECT count(*) AS n
FROM financial_facts ff
LEFT JOIN companies c ON c.id = ff.company_id
WHERE c.id IS NULL;

\echo '=== 7. Orphaned filings (company_id missing) ==='
SELECT count(*) AS n
FROM filings f
LEFT JOIN companies c ON c.id = f.company_id
WHERE c.id IS NULL;

\echo '=== 8. Orphaned listings (company or exchange missing) ==='
SELECT count(*) AS n
FROM company_listings cl
LEFT JOIN companies c ON c.id = cl.company_id
LEFT JOIN exchanges e ON e.id = cl.exchange_id
WHERE c.id IS NULL OR e.id IS NULL;

\echo '=== 9. Facts with NULL value ==='
SELECT count(*) AS n
FROM financial_facts
WHERE value IS NULL;

\echo '=== 10. Companies with no financial facts ==='
SELECT count(*) AS n
FROM companies c
LEFT JOIN financial_facts ff ON ff.company_id = c.id
WHERE ff.id IS NULL;

\echo '=== 11. Companies with no filings ==='
SELECT count(*) AS n
FROM companies c
LEFT JOIN filings f ON f.company_id = c.id
WHERE f.id IS NULL;

\echo '=== 12. Companies with no identifiers ==='
SELECT count(*) AS n
FROM companies c
LEFT JOIN company_identifiers ci ON ci.company_id = c.id
WHERE ci.id IS NULL;

\echo '=== 13. Facts without provenance (missing filing_id or provider_id) ==='
SELECT
  count(*) FILTER (WHERE provider_id IS NULL) AS missing_provider_id,
  count(*) FILTER (WHERE filing_id IS NULL) AS missing_filing_id,
  count(*) FILTER (WHERE source_id IS NULL) AS missing_source_id
FROM financial_facts;

\echo '=== 14. Facts referencing a non-existent filing ==='
SELECT count(*) AS n
FROM financial_facts ff
LEFT JOIN filings f ON f.id = ff.filing_id
WHERE ff.filing_id IS NOT NULL AND f.id IS NULL;
