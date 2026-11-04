-- 0022_normalization_v0.2.sql
-- IFRS/US-GAAP normalization, derived balance and quality issues.
-- financial_facts is never altered by this migration.

BEGIN;

CREATE TABLE IF NOT EXISTS concept_normalization (
  namespace text NOT NULL,
  concept text NOT NULL,
  field text NOT NULL,
  normalized_concept text NOT NULL,
  combine text,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (namespace, concept)
);

INSERT INTO concept_normalization
  (namespace, concept, field, normalized_concept, combine, notes) VALUES
  ('*', 'AccountsPayableAndAccruedLiabilitiesCurrent', 'accounts_payable', 'AccountsPayableCurrent', NULL, NULL),
  ('*', 'AccountsPayableCurrent', 'accounts_payable', 'AccountsPayableCurrent', NULL, NULL),
  ('*', 'AccountsReceivableNet', 'accounts_receivable', 'AccountsReceivableNetCurrent', NULL, NULL),
  ('*', 'AccountsReceivableNetCurrent', 'accounts_receivable', 'AccountsReceivableNetCurrent', NULL, NULL),
  ('*', 'AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment', 'ppe_accumulated_depreciation', 'AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment', NULL, NULL),
  ('*', 'Assets', 'total_assets', 'Assets', NULL, NULL),
  ('*', 'AssetsCurrent', 'current_assets', 'AssetsCurrent', NULL, NULL),
  ('*', 'AssetsTotal', 'total_assets', 'Assets', NULL, NULL),
  ('*', 'CapitalExpenditure', 'capital_expenditure', 'PaymentsToAcquirePropertyPlantAndEquipment', NULL, NULL),
  ('*', 'CapitalExpenditures', 'capital_expenditure', 'PaymentsToAcquirePropertyPlantAndEquipment', NULL, NULL),
  ('*', 'CashAndCashEquivalents', 'cash_and_equivalents', 'CashAndCashEquivalentsAtCarryingValue', NULL, NULL),
  ('*', 'CashAndCashEquivalentsAtCarryingValue', 'cash_and_equivalents', 'CashAndCashEquivalentsAtCarryingValue', NULL, NULL),
  ('*', 'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents', 'cash_and_equivalents', 'CashAndCashEquivalentsAtCarryingValue', NULL, NULL),
  ('*', 'CommonStockSharesOutstanding', 'shares_outstanding', 'WeightedAverageNumberOfDilutedSharesOutstanding', NULL, NULL),
  ('*', 'CostOfGoodsAndServicesSold', 'cogs', 'CostOfRevenue', NULL, NULL),
  ('*', 'CostOfGoodsSold', 'cogs', 'CostOfRevenue', NULL, NULL),
  ('*', 'CostOfGoodsSoldDepreciationDepletionAndAmortization', 'depreciation_amortization', 'DepreciationDepletionAndAmortization', NULL, NULL),
  ('*', 'CostOfRevenue', 'cogs', 'CostOfRevenue', NULL, NULL),
  ('*', 'CostOfSales', 'cogs', 'CostOfRevenue', NULL, NULL),
  ('*', 'CostsAndExpenses', 'operating_expense', 'OperatingExpenses', NULL, NULL),
  ('*', 'DebtCurrent', 'total_debt', 'LongTermDebt', NULL, NULL),
  ('*', 'DebtNoncurrent', 'total_debt', 'LongTermDebt', NULL, NULL),
  ('*', 'Depreciation', 'depreciation_amortization', 'DepreciationDepletionAndAmortization', NULL, NULL),
  ('*', 'DepreciationAmortizationAndAccretionNet', 'depreciation_amortization', 'DepreciationDepletionAndAmortization', NULL, NULL),
  ('*', 'DepreciationAndAmortization', 'depreciation_amortization', 'DepreciationDepletionAndAmortization', NULL, NULL),
  ('*', 'DepreciationDepletionAndAmortization', 'depreciation_amortization', 'DepreciationDepletionAndAmortization', NULL, NULL),
  ('*', 'DividendsCommonStockCash', 'dividends_paid', 'PaymentsOfDividends', NULL, NULL),
  ('*', 'DividendsPaid', 'dividends_paid', 'PaymentsOfDividends', NULL, NULL),
  ('*', 'DividendsPreferredStock', 'preferred_dividends', 'DividendsPreferredStock', NULL, NULL),
  ('*', 'DividendsPreferredStockCash', 'preferred_dividends', 'DividendsPreferredStock', NULL, NULL),
  ('*', 'EBIT', 'ebit', 'EBIT', NULL, NULL),
  ('*', 'EBITDA', 'ebitda', 'EBITDA', NULL, NULL),
  ('*', 'EntityCommonStockSharesOutstanding', 'shares_outstanding', 'WeightedAverageNumberOfDilutedSharesOutstanding', NULL, NULL),
  ('*', 'Equity', 'stockholders_equity', 'StockholdersEquity', NULL, NULL),
  ('*', 'GeneralAndAdministrativeExpense', 'sga', 'SellingGeneralAndAdministrativeExpense', NULL, NULL),
  ('*', 'GrossProfit', 'gross_profit', 'GrossProfit', NULL, NULL),
  ('*', 'IncomeLossBeforeIncomeTaxes', 'pretax_income', 'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest', NULL, NULL),
  ('*', 'IncomeLossFromContinuingOperations', 'net_income', 'NetIncomeLoss', NULL, NULL),
  ('*', 'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest', 'pretax_income', 'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest', NULL, NULL),
  ('*', 'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments', 'pretax_income', 'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest', NULL, NULL),
  ('*', 'IncomeTaxExpense', 'tax_provision', 'IncomeTaxExpenseBenefit', NULL, NULL),
  ('*', 'IncomeTaxExpenseBenefit', 'tax_provision', 'IncomeTaxExpenseBenefit', NULL, NULL),
  ('*', 'InterestExpense', 'interest_expense', 'InterestExpense', NULL, NULL),
  ('*', 'InterestExpenseNonoperating', 'interest_expense', 'InterestExpense', NULL, NULL),
  ('*', 'InventoryNet', 'inventory', 'InventoryNet', NULL, NULL),
  ('*', 'Liabilities', 'total_liabilities', 'Liabilities', NULL, NULL),
  ('*', 'LiabilitiesAndStockholdersEquity', 'total_assets', 'Assets', NULL, NULL),
  ('*', 'LiabilitiesCurrent', 'current_liabilities', 'LiabilitiesCurrent', NULL, NULL),
  ('*', 'LiabilitiesTotal', 'total_liabilities', 'Liabilities', NULL, NULL),
  ('*', 'LongTermDebt', 'total_debt', 'LongTermDebt', NULL, NULL),
  ('*', 'LongTermDebtNoncurrent', 'total_debt', 'LongTermDebt', NULL, NULL),
  ('*', 'LongTermLiabilities', 'long_term_liabilities', 'LongTermLiabilities', NULL, NULL),
  ('*', 'NetCashProvidedByUsedInOperatingActivities', 'operating_cash_flow', 'NetCashProvidedByUsedInOperatingActivities', NULL, NULL),
  ('*', 'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations', 'operating_cash_flow', 'NetCashProvidedByUsedInOperatingActivities', NULL, NULL),
  ('*', 'NetIncome', 'net_income', 'NetIncomeLoss', NULL, NULL),
  ('*', 'NetIncomeLoss', 'net_income', 'NetIncomeLoss', NULL, NULL),
  ('*', 'NetIncomeLossAvailableToCommonStockholdersBasic', 'net_income', 'NetIncomeLoss', NULL, NULL),
  ('*', 'NetIncomeLossAvailableToCommonStockholdersDiluted', 'net_income', 'NetIncomeLoss', NULL, NULL),
  ('*', 'NonoperatingIncomeExpense', 'non_operating_income_expense', 'NonoperatingIncomeExpense', NULL, NULL),
  ('*', 'OperatingCashFlow', 'operating_cash_flow', 'NetCashProvidedByUsedInOperatingActivities', NULL, NULL),
  ('*', 'OperatingExpenses', 'operating_expense', 'OperatingExpenses', NULL, NULL),
  ('*', 'OperatingIncome', 'operating_income', 'OperatingIncomeLoss', NULL, NULL),
  ('*', 'OperatingIncomeLoss', 'operating_income', 'OperatingIncomeLoss', NULL, NULL),
  ('*', 'OperatingLeaseIncome', 'revenue', 'Revenues', NULL, NULL),
  ('*', 'OperatingLeaseLeaseIncome', 'revenue', 'Revenues', NULL, NULL),
  ('*', 'OtherNonoperatingIncomeExpense', 'non_operating_income_expense', 'NonoperatingIncomeExpense', NULL, NULL),
  ('*', 'OtherRevenue', 'revenue', 'Revenues', 'sum', 'sum with OtherRevenue/RevenueFromSaleOfGoods when no total'),
  ('*', 'PaymentsForConstructionInProcess', 'capital_expenditure', 'PaymentsToAcquirePropertyPlantAndEquipment', NULL, NULL),
  ('*', 'PaymentsForRepurchaseOfCommonStock', 'repurchase_of_stock', 'PaymentsForRepurchaseOfEquity', NULL, NULL),
  ('*', 'PaymentsForRepurchaseOfEquity', 'repurchase_of_stock', 'PaymentsForRepurchaseOfEquity', NULL, NULL),
  ('*', 'PaymentsOfDividends', 'dividends_paid', 'PaymentsOfDividends', NULL, NULL),
  ('*', 'PaymentsOfDividendsCommonStock', 'dividends_paid', 'PaymentsOfDividends', NULL, NULL),
  ('*', 'PaymentsOfOrdinaryDividends', 'dividends_paid', 'PaymentsOfDividends', NULL, NULL),
  ('*', 'PaymentsToAcquireProductiveAssets', 'capital_expenditure', 'PaymentsToAcquirePropertyPlantAndEquipment', NULL, NULL),
  ('*', 'PaymentsToAcquirePropertyPlantAndEquipment', 'capital_expenditure', 'PaymentsToAcquirePropertyPlantAndEquipment', NULL, NULL),
  ('*', 'PreferredStockDividendsAndOtherAdjustments', 'preferred_dividends', 'DividendsPreferredStock', NULL, NULL),
  ('*', 'PretaxIncome', 'pretax_income', 'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest', NULL, NULL),
  ('*', 'ProfitLoss', 'net_income', 'NetIncomeLoss', NULL, NULL),
  ('*', 'ProfitLossFromOperatingActivities', 'operating_income', 'OperatingIncomeLoss', NULL, NULL),
  ('*', 'PropertyPlantAndEquipmentGross', 'ppe_gross', 'PropertyPlantAndEquipmentGross', NULL, NULL),
  ('*', 'PropertyPlantAndEquipmentNet', 'net_ppe', 'PropertyPlantAndEquipmentNet', NULL, NULL),
  ('*', 'RealEstateRevenueNet', 'revenue', 'Revenues', NULL, NULL),
  ('*', 'RegulatedAndUnregulatedOperatingRevenue', 'revenue', 'Revenues', NULL, NULL),
  ('*', 'RentalRevenue', 'revenue', 'Revenues', NULL, NULL),
  ('*', 'RepurchaseOfCommonStock', 'repurchase_of_stock', 'PaymentsForRepurchaseOfEquity', NULL, NULL),
  ('*', 'ResearchAndDevelopmentExpense', 'research_development', 'ResearchAndDevelopmentExpense', NULL, NULL),
  ('*', 'ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost', 'research_development', 'ResearchAndDevelopmentExpense', NULL, NULL),
  ('*', 'RetainedEarnings', 'retained_earnings', 'RetainedEarningsAccumulatedDeficit', NULL, NULL),
  ('*', 'RetainedEarningsAccumulatedDeficit', 'retained_earnings', 'RetainedEarningsAccumulatedDeficit', NULL, NULL),
  ('*', 'Revenue', 'revenue', 'Revenues', NULL, NULL),
  ('*', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'revenue', 'Revenues', NULL, NULL),
  ('*', 'RevenueFromContractWithCustomerIncludingAssessedTax', 'revenue', 'Revenues', NULL, NULL),
  ('*', 'RevenueFromContractsWithCustomers', 'revenue', 'Revenues', NULL, NULL),
  ('*', 'RevenueFromSaleOfGoods', 'revenue', 'Revenues', 'sum', 'sum with OtherRevenue/RevenueFromSaleOfGoods when no total'),
  ('*', 'Revenues', 'revenue', 'Revenues', NULL, NULL),
  ('*', 'RevenuesNetOfInterestExpense', 'bank_revenue', 'RevenuesNetOfInterestExpense', NULL, 'bank net-interest/interest income; not comparable to non-bank revenue'),
  ('*', 'SalesRevenueGoodsNet', 'revenue', 'Revenues', NULL, NULL),
  ('*', 'SalesRevenueNet', 'revenue', 'Revenues', NULL, NULL),
  ('*', 'SalesRevenueServicesNet', 'revenue', 'Revenues', NULL, NULL),
  ('*', 'SegmentExpenditureAdditionToLongLivedAssets', 'capital_expenditure', 'PaymentsToAcquirePropertyPlantAndEquipment', NULL, NULL),
  ('*', 'SellingGeneralAndAdministrativeExpense', 'sga', 'SellingGeneralAndAdministrativeExpense', NULL, NULL),
  ('*', 'ShareholdersEquity', 'stockholders_equity', 'StockholdersEquity', NULL, NULL),
  ('*', 'StockRepurchasedDuringPeriodValue', 'repurchase_of_stock', 'PaymentsForRepurchaseOfEquity', NULL, NULL),
  ('*', 'StockholdersEquity', 'stockholders_equity', 'StockholdersEquity', NULL, NULL),
  ('*', 'TotalEquityGrossMinorityInterest', 'stockholders_equity', 'StockholdersEquity', NULL, NULL),
  ('*', 'UtilitiesOperatingExpenseDepreciationAndAmortization', 'depreciation_amortization', 'DepreciationDepletionAndAmortization', NULL, NULL),
  ('*', 'WeightedAverageNumberOfDilutedSharesOutstanding', 'shares_outstanding', 'WeightedAverageNumberOfDilutedSharesOutstanding', NULL, NULL),
  ('*', 'WeightedAverageNumberOfShareOutstandingBasicAndDiluted', 'shares_outstanding', 'WeightedAverageNumberOfDilutedSharesOutstanding', NULL, NULL),
  ('*', 'WeightedAverageNumberOfSharesOutstanding', 'shares_outstanding', 'WeightedAverageNumberOfDilutedSharesOutstanding', NULL, NULL),
  ('*', 'WeightedAverageNumberOfSharesOutstandingBasic', 'shares_outstanding', 'WeightedAverageNumberOfDilutedSharesOutstanding', NULL, NULL),
  ('*', 'WeightedAverageNumberOfSharesOutstandingDiluted', 'shares_outstanding', 'WeightedAverageNumberOfDilutedSharesOutstanding', NULL, NULL),
  ('*', 'InterestAndDividendIncomeOperating', 'bank_revenue', 'InterestAndDividendIncomeOperating', NULL, 'bank net-interest/interest income; not comparable to non-bank revenue'),
  ('*', 'InterestIncomeExpenseNet', 'bank_revenue', 'InterestIncomeExpenseNet', NULL, 'bank net-interest/interest income; not comparable to non-bank revenue'),
  ('*', 'InterestIncomeOperating', 'bank_revenue', 'InterestIncomeOperating', NULL, 'bank net-interest/interest income; not comparable to non-bank revenue'),
  ('*', 'InterestRevenueExpense', 'bank_revenue', 'InterestRevenueExpense', NULL, 'bank net-interest/interest income; not comparable to non-bank revenue'),
  ('*', 'NoninterestIncome', 'bank_revenue', 'NoninterestIncome', NULL, 'bank net-interest/interest income; not comparable to non-bank revenue')
ON CONFLICT (namespace, concept) DO NOTHING;

CREATE OR REPLACE VIEW financial_facts_normalized AS
SELECT ff.id, ff.company_id, ff.fiscal_year, ff.fiscal_period,
       ff.period_start, ff.period_end, ff.namespace, ff.concept,
       ff.value, ff.unit,
       cn.field, cn.normalized_concept, cn.combine
FROM financial_facts ff
JOIN concept_normalization cn
  ON cn.concept = ff.concept
 AND (cn.namespace = '*' OR cn.namespace = ff.namespace);

CREATE MATERIALIZED VIEW IF NOT EXISTS core_financials AS
WITH revenue_parts AS (
  SELECT ff.company_id, ff.fiscal_year, ff.period_end,
    max(ff.value) FILTER (WHERE cn.combine IS NULL) AS total_rev,
    sum(ff.value) FILTER (WHERE cn.combine = 'sum') AS components_rev
  FROM financial_facts ff
  JOIN concept_normalization cn
    ON cn.concept = ff.concept
   AND (cn.namespace = '*' OR cn.namespace = ff.namespace)
  WHERE cn.field = 'revenue' AND ff.fiscal_period = 'FY'
  GROUP BY 1,2,3
), other_fields AS (
  SELECT ff.company_id, ff.fiscal_year, ff.period_end,
    max(ff.value) FILTER (WHERE cn.field = 'net_income') AS net_income,
    max(ff.value) FILTER (WHERE cn.field = 'operating_income') AS operating_income,
    max(ff.value) FILTER (WHERE cn.field = 'gross_profit') AS gross_profit,
    max(ff.value) FILTER (WHERE cn.field = 'total_assets') AS total_assets,
    max(ff.value) FILTER (WHERE cn.field = 'total_liabilities') AS total_liabilities,
    max(ff.value) FILTER (WHERE cn.field = 'stockholders_equity') AS stockholders_equity,
    max(ff.value) FILTER (WHERE cn.field = 'cash_and_equivalents') AS cash
  FROM financial_facts ff
  JOIN concept_normalization cn
    ON cn.concept = ff.concept
   AND (cn.namespace = '*' OR cn.namespace = ff.namespace)
  WHERE cn.field IN (
    'net_income','operating_income','gross_profit','total_assets',
    'total_liabilities','stockholders_equity','cash_and_equivalents'
  ) AND ff.fiscal_period = 'FY'
  GROUP BY 1,2,3
)
SELECT
  COALESCE(r.company_id, o.company_id) AS company_id,
  COALESCE(r.fiscal_year, o.fiscal_year) AS fiscal_year,
  COALESCE(r.period_end, o.period_end) AS period_end,
  COALESCE(r.total_rev, r.components_rev) AS revenue,
  o.net_income, o.operating_income, o.gross_profit,
  o.total_assets, o.total_liabilities, o.stockholders_equity, o.cash
FROM revenue_parts r
FULL OUTER JOIN other_fields o
  ON r.company_id = o.company_id
 AND r.fiscal_year = o.fiscal_year
 AND r.period_end = o.period_end;

CREATE UNIQUE INDEX IF NOT EXISTS idx_core_financials_company_period
  ON core_financials (company_id, fiscal_year, period_end);
CREATE INDEX IF NOT EXISTS idx_core_financials_company_year
  ON core_financials (company_id, fiscal_year);

CREATE OR REPLACE VIEW balance_effective AS
SELECT company_id, fiscal_year, period_end,
  total_assets,
  COALESCE(total_liabilities, total_assets - stockholders_equity) AS liabilities_effective,
  (total_liabilities IS NULL AND total_assets IS NOT NULL
   AND stockholders_equity IS NOT NULL) AS liabilities_derived,
  stockholders_equity, cash
FROM core_financials;

CREATE TABLE IF NOT EXISTS data_quality_issues (
  company_id uuid REFERENCES companies(id),
  fiscal_year smallint,
  field text,
  issue_type text,
  severity text,
  value numeric,
  detected_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, fiscal_year, field, issue_type)
);

COMMIT;
