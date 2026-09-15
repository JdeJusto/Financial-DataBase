-- Ticker / CIK Health Check
-- Run against financial_database after any ticker->CIK mapping change.
--
-- Exposes the three mapping-defect classes that let XOM resolve to the wrong
-- (stub) entity. A healthy database returns empty result sets for all sections.
--
--   1. TRUE STUB companies: the company's own CIK appears in NONE of its
--      facts-bearing core accessions (10-K/10-Q/20-F/40-F family). Every
--      real filing it owns was filed by a different CIK, so the company row
--      swallowed facts belonging to another entity. (Agent-filed accessions
--      and 0-fact filings are excluded -- they are benign.)
--   2. MULTI-CIK: one active universe ticker mapped to multiple distinct CIKs.
--   3. ZERO-FACTS: an active universe ticker whose company has no facts.

\set ON_ERROR_STOP off

\echo '=== 1. TRUE STUB companies (own CIK in none of their facts-bearing core accessions) ==='
SELECT c.legal_name,
       ci.identifier_value AS company_cik,
       cl.ticker,
       count(*) AS n_facts_bearing_accessions
FROM companies c
JOIN company_identifiers ci
  ON ci.company_id = c.id
 AND ci.identifier_type = 'CIK'
JOIN company_listings cl
  ON cl.company_id = c.id
 AND cl.is_active = TRUE
WHERE NOT EXISTS (
    SELECT 1
    FROM filings f
    JOIN financial_facts ff ON ff.filing_id = f.id
    WHERE f.company_id = c.id
      AND f.form IN ('10-K','10-K/A','10-KT','10-KT/A','10-Q','10-Q/A','10-QT','10-QT/A',
                     '20-F','20-F/A','20-F/A','40-F','40-F/A')
      AND left(f.accession_number, 10) = ci.identifier_value
)
GROUP BY c.legal_name, ci.identifier_value, cl.ticker
ORDER BY ci.identifier_value;

\echo '=== 2. Single active universe ticker mapped to multiple distinct CIKs ==='
SELECT cl.ticker,
       count(DISTINCT ci.identifier_value) AS n_ciks,
       string_agg(DISTINCT ci.identifier_value, ', ' ORDER BY ci.identifier_value) AS ciks,
       string_agg(DISTINCT c.legal_name, ' | ' ORDER BY c.legal_name) AS companies
FROM company_listings cl
JOIN companies c ON c.id = cl.company_id
JOIN company_identifiers ci
  ON ci.company_id = c.id
 AND ci.identifier_type = 'CIK'
WHERE cl.is_active = TRUE
GROUP BY cl.ticker
HAVING count(DISTINCT ci.identifier_value) > 1
ORDER BY cl.ticker;

\echo '=== 3. Active universe ticker with zero financial facts ==='
SELECT cl.ticker,
       c.legal_name,
       ci.identifier_value AS cik
FROM company_listings cl
JOIN companies c ON c.id = cl.company_id
LEFT JOIN company_identifiers ci
  ON ci.company_id = c.id
 AND ci.identifier_type = 'CIK'
WHERE cl.is_active = TRUE
  AND NOT EXISTS (SELECT 1 FROM financial_facts ff WHERE ff.company_id = c.id)
ORDER BY cl.ticker;
