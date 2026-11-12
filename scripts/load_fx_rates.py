"""Load historical FX rates (USD per unit) into ``fx_rates``.

Primary source: ECB euro reference rates (official, no key). Currencies the
ECB does not publish fall back to Yahoo (``<CCY>USD=X``), which is already an
optional dependency of the price providers.

Rates are stored per (currency, date); the ``core_financials`` view joins the
latest rate on or before each fact's ``period_end`` (weekends/holidays use the
previous business day). Missing rates are left absent, never replaced with 1.

Usage:
    python -m scripts.load_fx_rates
    python -m scripts.load_fx_rates --start 1999-01-01 --no-fallback
    python -m scripts.load_fx_rates --currencies EUR,GBP,JPY
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from financial_database.db.connection import get_connection
from financial_database.fx import (
    ECB_CURRENCIES,
    SUPPORTED_CURRENCIES,
    fetch_ecb_series,
    fetch_yfinance_series,
    today_utc,
    upsert_rates,
    usd_per_unit_from_eur,
)


def _db_currencies(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT code FROM fx_currencies ORDER BY code")
        return [row["code"] for row in cur.fetchall()]


def load_currency(
    conn,
    currency: str,
    start: date,
    end: date,
    usd_per_eur: dict[date, float] | None,
    *,
    fallback: bool,
) -> tuple[str, int]:
    """Load one currency; return ``(source, rows)``."""
    if currency == "USD":
        return "usd (implicit)", 0

    if (currency in ECB_CURRENCIES or currency == "EUR") and usd_per_eur:
        if currency in {"EUR", "USD"}:
            rates = dict(usd_per_eur)
        else:
            per_eur = fetch_ecb_series(currency, start, end)
            rates = usd_per_unit_from_eur(currency, per_eur, usd_per_eur)
        if rates:
            return "ecb", upsert_rates(conn, currency, rates.items(), "ecb")

    if fallback:
        rates = fetch_yfinance_series(currency, start, end)
        if rates:
            return "yfinance", upsert_rates(conn, currency, rates.items(), "yfinance")
    return "", 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=date(1999, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=today_utc())
    parser.add_argument(
        "--currencies",
        default="",
        help="Comma-separated subset (default: all fx_currencies)",
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="ECB only; do not call Yahoo for currencies ECB does not publish",
    )
    args = parser.parse_args(argv)

    with get_connection() as conn:
        selected = (
            [
                part.strip().upper()
                for part in args.currencies.split(",")
                if part.strip()
            ]
            if args.currencies
            else _db_currencies(conn)
        )
        unknown = [code for code in selected if code not in SUPPORTED_CURRENCIES]
        if unknown:
            print(f"Unknown currencies: {', '.join(unknown)}", file=sys.stderr)
            return 2

        usd_per_eur: dict[date, float] = {}
        if "USD" in selected or any(code in ECB_CURRENCIES for code in selected):
            print("Fetching ECB USD/EUR series...", flush=True)
            usd_per_eur = fetch_ecb_series("USD", args.start, args.end)
            print(f"  {len(usd_per_eur)} EUR/USD observations", flush=True)

        total = 0
        failures: list[str] = []
        for currency in selected:
            source, rows = load_currency(
                conn,
                currency,
                args.start,
                args.end,
                usd_per_eur,
                fallback=not args.no_fallback,
            )
            total += rows
            if rows:
                print(f"  {currency}: {rows} rows ({source})", flush=True)
            elif currency != "USD":
                failures.append(currency)
                print(f"  {currency}: no rates", file=sys.stderr)

    print(f"Loaded {total} FX rows; {len(failures)} currencies without rates")
    if failures:
        print(
            "No rates (value_usd will be NULL for these): "
            + ", ".join(sorted(failures))
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
