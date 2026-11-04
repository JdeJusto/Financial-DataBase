# IFRS cross-validation vs yfinance — pre-FDB 0.2.0

Date: 2026-11-04. Status: **Phase 0 gate before the normalization migration.**

## Method

- FDB source: latest annual (`fiscal_period='FY'`) `ifrs-full` fact, latest
  `fiscal_year`/`period_end`.
- Equity: FDB `Equity` vs yfinance **Total Equity Gross Minority Interest**
  (the NCI-inclusive total; falls back to Stockholders Equity when absent).
- Revenue: FDB total revenue (`Revenue`, `RevenueFromContractsWithCustomers`
  or `RevenueFromSaleOfGoods + OtherRevenue`) vs the yfinance line that
  matches the concept:
  - total-revenue concepts → yfinance **Total Revenue**;
  - contract/operating concepts → yfinance **Operating Revenue** when it
    exists.
  Both columns are reported for transparency.
- Currency: comparison is only meaningful when both sides use the reporting
  currency; FDB units are shown.
- 18 IFRS tickers from the top of the `ifrs-full` fact table.

## Results

| Ticker | FY | Unit | Equity diff | Revenue (selected) | Revenue total diff | Revenue operating diff | Verdict |
|---|---:|---|---:|---:|---:|---:|---|
| SAN | 2025 | EUR | 0.00 % | bank net-interest vs gross | 23.59 % | 23.59 % | Equity OK; revenue definition differs (bank) |
| BNS | 2025 | CAD | 0.00 % | total | 1.74 % | 1.74 % | OK |
| FMS | 2025 | EUR | 0.00 % | total | 0.00 % | 0.00 % | OK |
| CM | 2025 | CAD | 0.00 % | total | 0.41 % | 0.41 % | OK |
| BMO | 2025 | CAD | 0.00 % | total | 0.48 % | 0.48 % | OK |
| RY | 2025 | CAD | 0.00 % | total | 0.11 % | 0.11 % | OK |
| NOMD | 2025 | EUR | 0.00 % | total | 0.00 % | 0.00 % | OK |
| TD | 2025 | CAD | 0.00 % | bank net-interest vs gross | 10.60 % | 10.60 % | Equity OK; revenue definition differs (bank) |
| B | 2025 | USD | 0.00 % | total | 0.00 % | 0.00 % | OK |
| CCEP | 2025 | EUR | 0.00 % | total | 0.00 % | 0.00 % | OK |
| BBVA | 2025 | EUR | 0.00 % | n/a (yfinance revenue absent) | — | — | Equity OK; revenue not comparable |
| RIO | 2025 | USD | 0.00 % | total | 0.00 % | 0.00 % | OK |
| SHEL | 2025 | USD | 0.00 % | total | 0.00 % | 0.00 % | OK |
| TTE | 2025 | USD | 0.00 % | operating/contract | 10.34 % | **0.00 %** | OK vs Operating Revenue |
| AZN | 2025 | USD | 0.00 % | total | 0.00 % | 0.00 % | OK |
| SNY | 2025 | EUR | 0.00 % | total | **0.00 %** | 7.08 % | OK vs Total Revenue |
| EQNR | 2025 | USD | 0.00 % | total | 0.60 % | 1.16 % | OK |
| HSBC | 2025 | USD | 0.00 % | n/a (yfinance revenue absent) | — | — | Equity OK; revenue not comparable |

## Findings

- **Equity: 18/18 within 5 % (all 0.00 %)**. The `Equity` → NCI-inclusive
  total mapping is correct.
- **Revenue: 14/18 comparable within 5 %** once the comparator matches the
  concept:
  - TTE's FDB `RevenueFromContractsWithCustomers` matches Operating
    Revenue exactly; yfinance's Total Revenue excludes excise taxes.
  - SNY's FDB total matches Total Revenue; Operating Revenue is a subset.
- **SAN and TD (2 tickers) exceed 5 % on revenue** because their FDB
  top-line is net interest/revenues-net-of-interest, while yfinance reports
  a gross total. This is a **definition difference, not a mapping error**;
  both are documented and their revenue is excluded from the mapping
  validation. Equity remains validated.
- **BBVA and HSBC** have no comparable yfinance revenue row; equity
  validated.
- Threshold check: 2 tickers >5 % on revenue (after comparator alignment),
  below the ">3 tickers" stop threshold. No ticker is excluded from the
  `core_financials` MV: the MV maps **concepts**, not tickers, and the
  bank-revenue concept is a separate mapping row.

## Decision

Proceed to the FDB 0.2.0 migration with:

- Equity mapping validated (18/18).
- Revenue mapping validated for the non-bank concept set (14/14 comparable);
  the two bank top-line exceptions are documented, not silently normalized.
- No global mapping changes required by this validation.
