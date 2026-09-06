-- Reusable SQL script for financial time series
-- Takes a CIK as parameter (:cik)
-- Returns yearly financial metrics with growth rates and margins

WITH company_data AS (
    SELECT
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
        -- Total assets concepts
        COALESCE(
            MAX(CASE WHEN f.concept IN ('Assets', 'AssetsTotal') THEN f.value END)::numeric,
            0
        ) as total_assets,
        -- Stockholders equity concepts
        COALESCE(
            MAX(CASE WHEN f.concept IN ('StockholdersEquity', 'ShareholdersEquity', 'TotalEquity') THEN f.value END)::numeric,
            0
        ) as stockholders_equity,
        -- Total liabilities concepts
        COALESCE(
            MAX(CASE WHEN f.concept IN ('Liabilities', 'LiabilitiesTotal') THEN f.value END)::numeric,
            0
        ) as total_liabilities,
        -- Operating cash flow concepts
        COALESCE(
            MAX(CASE WHEN f.concept IN ('OperatingCashFlow', 'NetCashProvidedByUsedInOperatingActivities') THEN f.value END)::numeric,
            0
        ) as operating_cash_flow,
        -- Capex concepts
        COALESCE(
            MAX(CASE WHEN f.concept IN ('CapitalExpenditures', 'PaymentsToAcquirePropertyPlantAndEquipment') THEN f.value END)::numeric,
            0
        ) as capex
    FROM companies c
    JOIN company_identifiers ci ON c.id = ci.company_id
        AND ci.identifier_type = 'CIK'
        AND ci.provider_id = (
            SELECT id FROM data_providers WHERE name = 'SEC EDGAR'
        )
    JOIN financial_facts f ON c.id = f.company_id
    WHERE ci.identifier_value = :cik
        AND f.fiscal_year IS NOT NULL
        AND f.fiscal_year > 0
    GROUP BY c.id, f.fiscal_year
),
calculations AS (
    SELECT
        fiscal_year,
        revenue,
        net_income,
        total_assets,
        stockholders_equity,
        total_liabilities,
        operating_cash_flow,
        capex,
        -- Calculate free cash flow (Operating CF - Capex)
        (operating_cash_flow - capex) as free_cash_flow,
        -- Calculate growth rates (compared to previous year)
        LAG(revenue) OVER (ORDER BY fiscal_year) as prev_revenue,
        LAG(net_income) OVER (ORDER BY fiscal_year) as prev_net_income,
        LAG(total_assets) OVER (ORDER BY fiscal_year) as prev_total_assets,
        LAG(stockholders_equity) OVER (ORDER BY fiscal_year) as prev_stockholders_equity
    FROM company_data
)
SELECT
    fiscal_year,
    revenue,
    net_income,
    total_assets,
    stockholders_equity,
    total_liabilities,
    operating_cash_flow,
    capex,
    free_cash_flow,
    -- Growth rates
    CASE
        WHEN prev_revenue IS NOT NULL AND prev_revenue != 0
        THEN ((revenue - prev_revenue) / prev_revenue) * 100
        ELSE NULL
    END as revenue_growth_pct,
    CASE
        WHEN prev_net_income IS NOT NULL AND prev_net_income != 0
        THEN ((net_income - prev_net_income) / prev_net_income) * 100
        ELSE NULL
    END as net_income_growth_pct,
    CASE
        WHEN prev_total_assets IS NOT NULL AND prev_total_assets != 0
        THEN ((total_assets - prev_total_assets) / prev_total_assets) * 100
        ELSE NULL
    END as total_assets_growth_pct,
    -- Margins
    CASE
        WHEN revenue IS NOT NULL AND revenue != 0
        THEN (net_income / revenue) * 100
        ELSE NULL
    END as net_margin_pct,
    CASE
        WHEN revenue IS NOT NULL AND revenue != 0
        THEN (operating_cash_flow / revenue) * 100
        ELSE NULL
    END as operating_margin_pct,
    CASE
        WHEN revenue IS NOT NULL AND revenue != 0
        THEN (free_cash_flow / revenue) * 100
        ELSE NULL
    END as fcf_margin_pct
FROM calculations
ORDER BY fiscal_year;