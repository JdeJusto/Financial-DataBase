#!/usr/bin/env python3
"""
Select a diverse sample of SEC companies for stress testing.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from financial_database.providers.sec.client import SECClient

# Predefined list of large-cap tickers (we'll map to CIKs)
LARGE_CAP_TICKERS = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "GOOGL": "Alphabet Inc. (Class A)",
    "GOOG": "Alphabet Inc. (Class C)",
    "AMZN": "Amazon.com, Inc.",
    "TSLA": "Tesla, Inc.",
    "META": "Meta Platforms, Inc.",
    "BRK.B": "Berkshire Hathaway Inc. (Class B)",
    "UNH": "UnitedHealth Group Incorporated",
    "JNJ": "Johnson & Johnson",
    "V": "Visa Inc.",
    "WMT": "Walmart Inc.",
    "PG": "Procter & Gamble Company",
    "MA": "Mastercard Incorporated",
    "HD": "Home Depot, Inc.",
    "BAC": "Bank of America Corporation",
    "XOM": "Exxon Mobil Corporation",
    "PFE": "Pfizer Inc.",
    "KO": "The Coca-Cola Company",
    "PEP": "PepsiCo, Inc.",
    "AVGO": "Broadcom Inc.",
    "COST": "Costco Wholesale Corporation",
    "MRK": "Merck & Co., Inc.",
    "ABT": "Abbott Laboratories",
    "NFLX": "Netflix, Inc.",
    "ADBE": "Adobe Inc.",
    "CRM": "Salesforce, Inc.",
    "CSCO": "Cisco Systems, Inc.",
    "ACN": "Accenture plc",
    "LIN": "Linde plc",
    "TXN": "Texas Instruments Incorporated",
    "HON": "Honeywell International Inc.",
    "LOW": "Lowe's Companies, Inc.",
    "UNP": "Union Pacific Corporation",
    "UPS": "United Parcel Service, Inc.",
    "PM": "Philip Morris International Inc.",
    "AMD": "Advanced Micro Devices, Inc.",
    "QCOM": "QUALCOMM Incorporated",
    "SBUX": "Starbucks Corporation",
    "INTU": "Intuit Inc.",
    "AMGN": "Amgen Inc.",
    "CAT": "Caterpillar Inc.",
    "VZ": "Verizon Communications Inc.",
    "IBM": "International Business Machines Corporation",
    "GS": "Goldman Sachs Group, Inc.",
    "AXP": "American Express Company",
    "BLK": "BlackRock, Inc.",
    "SPGI": "S&P Global Inc.",
    "MO": "Altria Group, Inc.",
    "T": "AT&T Inc.",
    "BMY": "Bristol-Myers Squibb Company",
    "DHR": "Danaher Corporation",
    "ETN": "Eaton Corporation plc",
    "GE": "General Electric Company",
    "ISRG": "Intuitive Surgical, Inc.",
    "MDT": "Medtronic plc",
    "MMC": "Marsh & McLennan Companies, Inc.",
    "MMM": "3M Company",
    "NKE": "NIKE, Inc.",
    "NOW": "ServiceNow, Inc.",
    "ORCL": "Oracle Corporation",
    "RTX": "Raytheon Technologies Corporation",
    "SCHW": "Charles Schwab Corporation",
    "SO": "Southern Company",
    "USB": "U.S. Bancorp",
    "C": "Citigroup Inc.",
    "DE": "Deere & Company",
    "DIS": "The Walt Disney Company",
    "PLD": "Prologis, Inc.",
    "TJX": "TJX Companies, Inc.",
    "UBER": "Uber Technologies, Inc.",
    "VLO": "Valero Energy Corporation",
    "WFC": "Wells Fargo & Company",
    "MCD": "McDonald's Corporation",
    "ET": "Energy Transfer LP",
    "CVX": "Chevron Corporation",
    "SRE": "Sempra",
    "SHW": "Sherwin-Williams Company",
    "F": "Ford Motor Company",
    "GM": "General Motors Company",
}


async def main():
    # Set the user agent from environment
    user_agent = os.environ.get("SEC_USER_AGENT")
    if not user_agent:
        print("ERROR: SEC_USER_AGENT environment variable must be set")
        sys.exit(1)

    async with SECClient(user_agent=user_agent) as client:
        print("Fetching SEC company tickers...")
        companies = await client.get_company_tickers()
        print(f"Found {len(companies)} companies")

        # Build a mapping from ticker to CIK for quick lookup
        ticker_to_cik = {}
        for company in companies:
            if company.ticker:
                ticker_to_cik[company.ticker] = company.cik

        # 1. Large-cap US companies (by ticker)
        large_cap_ciks = set()
        for ticker in LARGE_CAP_TICKERS:
            if ticker in ticker_to_cik:
                large_cap_ciks.add(ticker_to_cik[ticker])
            else:
                print(f"Warning: Ticker {ticker} not found in SEC data")

        print(f"Selected {len(large_cap_ciks)} large-cap companies")

        # 2. US companies (exchange in US list) with ticker, not in large-cap
        us_exchanges = {"NYSE", "NASDAQ", "AMEX"}
        us_ciks = set()
        for company in companies:
            if (
                company.exchange in us_exchanges
                and company.ticker
                and company.cik not in large_cap_ciks
            ):
                us_ciks.add(company.cik)

        # We want 50 small-cap US companies
        small_cap_ciks = set()
        # We'll take the first 50 from the list (sorted by CIK for determinism)
        sorted_us_ciks = sorted(us_ciks)
        for cik in sorted_us_ciks[:50]:
            small_cap_ciks.add(cik)
        print(f"Selected {len(small_cap_ciks)} small-cap US companies")

        # 3. Foreign private issuers: non-US exchange with ticker
        foreign_ciks = set()
        for company in companies:
            if (
                company.exchange not in us_exchanges
                and company.exchange
                and company.ticker
            ):
                foreign_ciks.add(company.cik)

        # We want 30 foreign companies
        sorted_foreign_ciks = sorted(foreign_ciks)
        foreign_selected = set(sorted_foreign_ciks[:30])
        print(f"Selected {len(foreign_selected)} foreign private issuers")

        # 4. Companies with no ticker (CIK only)
        no_ticker_ciks = set()
        for company in companies:
            if not company.ticker:
                no_ticker_ciks.add(company.cik)

        # We want 20 companies with no ticker
        sorted_no_ticker_ciks = sorted(no_ticker_ciks)
        no_ticker_selected = set(sorted_no_ticker_ciks[:20])
        print(f"Selected {len(no_ticker_selected)} companies with no ticker")

        # 5. Fill the rest to reach 750 total (or between 500-1000)
        selected_ciks = set()
        selected_ciks.update(large_cap_ciks)
        selected_ciks.update(small_cap_ciks)
        selected_ciks.update(foreign_selected)
        selected_ciks.update(no_ticker_selected)

        print(f"Currently selected: {len(selected_ciks)} companies")

        # We want at least 500, up to 1000. Let's aim for 750.
        target = 750
        remaining_needed = target - len(selected_ciks)
        if remaining_needed > 0:
            # Get all remaining companies (not already selected) and sort by CIK
            remaining_ciks = [
                company.cik for company in companies if company.cik not in selected_ciks
            ]
            remaining_ciks.sort()
            # Take the first 'remaining_needed' companies
            fill_ciks = set(remaining_ciks[:remaining_needed])
            selected_ciks.update(fill_ciks)
            print(f"Added {len(fill_ciks)} companies to reach target")

        # Final count
        print(f"Total selected companies: {len(selected_ciks)}")

        # Save to file
        output_file = Path("data/stress_test_ciks.txt")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text("\n".join(sorted(selected_ciks)) + "\n")
        print(f"Saved selected CIKs to {output_file}")

        # Also, let's print some stats
        print("\nSelection stats:")
        print(f"  Large-cap US: {len(large_cap_ciks)}")
        print(f"  Small-cap US: {len(small_cap_ciks)}")
        print(f"  Foreign: {len(foreign_selected)}")
        print(f"  No ticker: {len(no_ticker_selected)}")
        print(
            f"  Fill: {len(selected_ciks) - len(large_cap_ciks) - len(small_cap_ciks) - len(foreign_selected) - len(no_ticker_selected)}"
        )


if __name__ == "__main__":
    asyncio.run(main())
