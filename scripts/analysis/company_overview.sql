-- Reusable SQL script for company overview
-- Takes a CIK as parameter (%(cik)s)
-- Returns key company information

SELECT
    c.legal_name,
    c.sector,
    c.industry,
    c.country as country,
    MIN(f.fiscal_year) as earliest_fiscal_year,
    MAX(f.fiscal_year) as latest_fiscal_year,
    COUNT(DISTINCT f.id) as total_facts,
    COUNT(DISTINCT fi.id) as total_filings
FROM companies c
LEFT JOIN company_identifiers ci ON c.id = ci.company_id
    AND ci.identifier_type = 'CIK'
    AND ci.provider_id = (
        SELECT id FROM data_providers WHERE name = 'SEC EDGAR'
    )
LEFT JOIN financial_facts f ON c.id = f.company_id
LEFT JOIN filings fi ON c.id = fi.company_id
WHERE ci.identifier_value = %(cik)s
GROUP BY c.legal_name, c.sector, c.industry, c.country;