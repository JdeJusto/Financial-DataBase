-- Reusable SQL script for comparing multiple companies
-- Takes a list of CIKs as parameters (using array placeholder :ciks)
-- Returns a comparison table with key metrics for latest fiscal year:
-- * revenue
-- * net_income
-- * ROE
-- * net margin
-- * debt_to_equity
-- * revenue growth (latest vs previous year)

WITH company_list AS (
    -- Convert array of CIKs to rows (PostgreSQL specific)
    SELECT unnest(:ciks::text[]) as cik
),
yearly_data AS (
    SELECT
        cl.cik,
        c.id as company_id,
        f.fiscal_year,
        -- Revenue concepts
        COALESCE(
            MAX(CASE WHEN f.concept IN ('Revenues', 'Revenue', 'SalesRevenueNet', 'RevenueFromContractWithCustomerExcludingAssessedTax') THEN f.value END)::numeric,
            0
        ) as revenue,
        -- Net income concepts
        COALESCE(
            MAX(CASE WHEN f.concept IN ('NetIncomeLoss', 'ProfitLoss', 'NetIncome') THEN f.value END)::numeric,
            0
        ) as net_income,
        -- Stockholders equity concepts
        COALESCE(
            MAX(CASE WHEN f.concept IN ('StockholdersEquity', 'ShareholdersEquity', 'TotalEquity') THEN f.value END)::numeric,
            0
        ) as stockholders_equity,
        -- Total liabilities concepts
        COALESCE(
            MAX(CASE WHEN f.concept IN ('Liabilities', 'LiabilitiesTotal') THEN f.value END)::numeric,
            0
        ) as total_liabilities
    FROM company_list cl
    JOIN companies c ON c.id = (
        SELECT ci.company_id
        FROM company_identifiers ci
        JOIN data_providers dp ON ci.provider_id = dp.id
        WHERE ci.identifier_type = 'CIK'
            AND ci.identifier_value = cl.cik
            AND dp.name = 'SEC EDGAR'
        LIMIT 1
    )
    JOIN financial_facts f ON c.id = f.company_id
    WHERE f.fiscal_year IS NOT NULL
      AND f.fiscal_year > 0
    GROUP BY cl.cik, c.id, f.fiscal_year
),
latest_financials AS (
    SELECT
        yd.cik,
        yd.company_id,
        yd.fiscal_year,
        yd.revenue,
        yd.net_income,
        yd.stockholders_equity,
        yd.total_liabilities,
        -- Calculate ROE
        CASE
            WHEN yd.stockholders_equity IS NOT NULL AND yd.stockholders_equity != 0
            THEN (yd.net_income / yd.stockholders_equity) * 100
            ELSE NULL
        END as roe_pct,
        -- Calculate net margin
        CASE
            WHEN yd.revenue IS NOT NULL AND yd.revenue != 0
            THEN (yd.net_income / yd.revenue) * 100
            ELSE NULL
        END as net_margin_pct,
        -- Calculate debt to equity
        CASE
            WHEN yd.stockholders_equity IS NOT NULL AND yd.stockholders_equity != 0
            THEN yd.total_liabilities / yd.stockholders_equity
            ELSE NULL
        END as debt_to_equity
    FROM yearly_data yd
    WHERE (yd.cik, yd.fiscal_year) IN (
        SELECT cik, MAX(fiscal_year)
        FROM yearly_data
        GROUP BY cik
    )
),
previous_year AS (
    SELECT
        cl.cik,
        yd.fiscal_year - 1 as prev_fiscal_year,
        yd.revenue as prev_revenue,
        yd.fiscal_year as prev_fiscal_year_col
    FROM company_list cl
    JOIN companies c ON c.id = (
        SELECT ci.company_id
        FROM company_identifiers ci
        JOIN data_providers dp ON ci.provider_id = dp.id
        WHERE ci.identifier_type = 'CIK'
            AND ci.identifier_value = cl.cik
            AND dp.name = 'SEC EDGAR'
        LIMIT 1
    )
    JOIN yearly_data yd ON yd.cik = cl.cik
    WHERE yd.fiscal_year IS NOT NULL
      AND yd.fiscal_year > 0
),
revenue_growth AS (
    SELECT
        lf.cik,
        lf.fiscal_year,
        lf.revenue,
        lf.net_income,
        lf.roe_pct,
        lf.net_margin_pct,
        lf.debt_to_equity,
        CASE
            WHEN pr.prev_revenue IS NOT NULL AND pr.prev_revenue != 0
            THEN ((lf.revenue - pr.prev_revenue) / pr.prev_revenue) * 100
            ELSE NULL
        END as revenue_growth_pct
    FROM latest_financials lf
    JOIN previous_year pr ON lf.cik = pr.cik AND lf.fiscal_year = pr.prev_fiscal_year_col + 1
)
SELECT
    lf.cik,
    lf.fiscal_year as latest_fiscal_year,
    lf.revenue,
    lf.net_income,
    lf.roe_pct,
    lf.net_margin_pct,
    lf.debt_to_equity,
    rg.revenue_growth_pct
FROM latest_financials lf
LEFT JOIN revenue_growth rg ON lf.cik = rg.cik AND lf.fiscal_year = rg.fiscal_year
ORDER BY lf.revenue DESC NULLS LAST;