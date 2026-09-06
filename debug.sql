WITH cik_list AS (
    SELECT trim(value) as cik
    FROM unnest(string_to_array('0000320193,0000789019', ',')) AS value
),
companies AS (
    SELECT
        c.id as company_id,
        c.legal_name,
        ci.identifier_value as cik,
        cl.ticker
    FROM companies c
    JOIN company_identifiers ci ON c.id = ci.company_id
    JOIN company_listings cl ON c.id = cl.company_id AND cl.is_active = true
    JOIN cik_list clist ON ci.identifier_value = clist.cik
    WHERE ci.identifier_type = 'CIK'
),
latest_financials AS (
    SELECT
        ff.company_id,
        ff.fiscal_year,
        -- Revenue
        COALESCE(
            MAX(CASE WHEN ff.concept IN ('Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet', 'RevenueFromSalesOfGoodsNet', 'RevenueFromServicesNet') THEN ff.value END),
            0
        ) as revenue,
        -- Net Income
        COALESCE(
            MAX(CASE WHEN ff.concept IN ('NetIncomeLoss', 'ProfitLoss', 'NetIncome') THEN ff.value END),
            0
        ) as net_income,
        -- Total Assets
        COALESCE(
            MAX(CASE WHEN ff.concept = 'Assets' THEN ff.value END),
            0
        ) as total_assets,
        -- Stockholders' Equity
        COALESCE(
            MAX(CASE WHEN ff.concept IN ('StockholdersEquity', 'ShareholdersEquity', 'TotalEquity') THEN ff.value END),
            0
        ) as stockholders_equity,
        -- Total Liabilities
        COALESCE(
            MAX(CASE WHEN ff.concept = 'Liabilities' THEN ff.value END),
            0
        ) as total_liabilities
    FROM financial_facts ff
    JOIN companies f ON ff.company_id = f.company_id
    WHERE ff.fiscal_period = 'FY'  -- Only yearly data
      AND ff.unit = 'USD'
    GROUP BY ff.company_id, ff.fiscal_year
),
ranked_financials AS (
    SELECT
        lf.*,
        ROW_NUMBER() OVER (PARTITION BY company_id ORDER BY fiscal_year DESC) as rn
    FROM latest_financials lf
),
latest AS (
    SELECT
        company_id,
        fiscal_year,
        revenue,
        net_income,
        total_assets,
        stockholders_equity,
        total_liabilities
    FROM ranked_financials
    WHERE rn = 1
)
SELECT * FROM latest LIMIT 5;