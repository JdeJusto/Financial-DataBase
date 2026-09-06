-- Reusable SQL script for advanced financial ratios
-- Takes a CIK as parameter (:cik)
-- Returns yearly ratios including ROE, ROA, debt ratios, and valuation ratios (if prices available)

WITH financials AS (
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
        -- Current assets (if available)
        COALESCE(
            MAX(CASE WHEN f.concept IN ('AssetsCurrent', 'CurrentAssets') THEN f.value END)::numeric,
            NULL
        ) as current_assets,
        -- Current liabilities (if available)
        COALESCE(
            MAX(CASE WHEN f.concept IN ('LiabilitiesCurrent', 'CurrentLiabilities') THEN f.value END)::numeric,
            NULL
        ) as current_liabilities,
        -- Shares outstanding (for EPS calculation)
        COALESCE(
            MAX(CASE WHEN f.concept IN ('CommonStockSharesOutstanding', 'CommonStockSharesOutstanding', 'EntityCommonStockSharesOutstanding') THEN f.value END)::numeric,
            NULL
        ) as shares_outstanding
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
price_data AS (
    -- Get latest price for each ticker (for valuation ratios)
    SELECT
        cl.ticker,
        p.close as latest_price,
        p.price_date
    FROM company_listings cl
    JOIN prices p ON cl.id = p.listing_id
    JOIN data_providers dp ON p.provider_id = dp.id
    WHERE dp.name = 'Yahoo Finance'
    AND p.price_date = (
        SELECT MAX(price_date)
        FROM prices p2
        JOIN company_listings cl2 ON p2.listing_id = cl2.id
        JOIN data_providers dp2 ON p2.provider_id = dp2.id
        WHERE dp2.name = 'Yahoo Finance'
        AND cl2.ticker = cl.ticker
    )
    AND cl.is_active = true
    AND cl.is_primary = true
),
calculations AS (
    SELECT
        f.company_id,
        f.fiscal_year,
        f.revenue,
        f.net_income,
        f.total_assets,
        f.stockholders_equity,
        f.total_liabilities,
        f.current_assets,
        f.current_liabilities,
        f.shares_outstanding,
        -- ROE (Return on Equity)
        CASE
            WHEN f.stockholders_equity IS NOT NULL AND f.stockholders_equity != 0
            THEN (f.net_income / f.stockholders_equity) * 100
            ELSE NULL
        END as roe_pct,
        -- ROA (Return on Assets)
        CASE
            WHEN f.total_assets IS NOT NULL AND f.total_assets != 0
            THEN (f.net_income / f.total_assets) * 100
            ELSE NULL
        END as roa_pct,
        -- Net Margin
        CASE
            WHEN f.revenue IS NOT NULL AND f.revenue != 0
            THEN (f.net_income / f.revenue) * 100
            ELSE NULL
        END as net_margin_pct,
        -- Debt to Equity
        CASE
            WHEN f.stockholders_equity IS NOT NULL AND f.stockholders_equity != 0
            THEN f.total_liabilities / f.stockholders_equity
            ELSE NULL
        END as debt_to_equity,
        -- Debt to Assets
        CASE
            WHEN f.total_assets IS NOT NULL AND f.total_assets != 0
            THEN f.total_liabilities / f.total_assets
            ELSE NULL
        END as debt_to_assets,
        -- Current Ratio
        CASE
            WHEN f.current_assets IS NOT NULL
                 AND f.current_liabilities IS NOT NULL
                 AND f.current_liabilities != 0
            THEN f.current_assets / f.current_liabilities
            ELSE NULL
        END as current_ratio
    FROM financials f
)
SELECT
    calc.fiscal_year,
    calc.revenue,
    calc.net_income,
    calc.total_assets,
    calc.stockholders_equity,
    calc.total_liabilities,
    calc.roe_pct,
    calc.roa_pct,
    calc.net_margin_pct,
    calc.debt_to_equity,
    calc.debt_to_assets,
    calc.current_ratio,
    -- Valuation ratios (require price data)
    CASE
        WHEN p.latest_price IS NOT NULL
             AND calc.shares_outstanding IS NOT NULL
             AND calc.shares_outstanding != 0
        THEN (p.latest_price * calc.shares_outstanding)  -- Market Cap
        ELSE NULL
    END as market_cap,
    CASE
        WHEN p.latest_price IS NOT NULL
             AND calc.net_income IS NOT NULL
             AND calc.net_income != 0
             AND calc.shares_outstanding IS NOT NULL
             AND calc.shares_outstanding != 0
        THEN (p.latest_price * calc.shares_outstanding) / calc.net_income  -- P/E = Market Cap / Net Income
        ELSE NULL
    END as pe_ratio
FROM calculations calc
LEFT JOIN company_listings cl ON cl.company_id = calc.company_id
    AND cl.is_active = true
    AND cl.is_primary = true
LEFT JOIN price_data p ON cl.ticker = p.ticker
ORDER BY calc.fiscal_year;