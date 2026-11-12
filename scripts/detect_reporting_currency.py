"""Detect and report non-USD reporting currencies in financial_facts.

The SEC XBRL ``unit`` already carries the filing currency (EUR, GBP, ...).
This script reports the distribution, backfills ``financial_facts.currency``
from the ``fx_currencies`` table, and lists the companies most affected.

It never changes ``value``; it only fills the nullable currency column.

Usage:
    python -m scripts.detect_reporting_currency
    python -m scripts.detect_reporting_currency --backfill
    python -m scripts.detect_reporting_currency --top 30
"""

from __future__ import annotations

import argparse

from financial_database.db.connection import get_connection


def _distribution(conn) -> list[tuple[str, int, int]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT unit, count(*) AS facts, count(DISTINCT company_id) AS companies
            FROM financial_facts
            WHERE unit ~ '^[A-Z]{3}(/shares)?$'
            GROUP BY unit
            ORDER BY facts DESC
            """
        )
        return [(row["unit"], row["facts"], row["companies"]) for row in cur.fetchall()]


def _backfill(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE financial_facts
            SET currency = unit
            WHERE currency IS NULL
              AND unit <> 'USD'
              AND unit IN (SELECT code FROM fx_currencies)
            """
        )
        updated = cur.rowcount
    conn.commit()
    return updated


def _top_companies(conn, limit: int) -> list[tuple[str, str, int]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT UPPER(cl.ticker) AS ticker, ff.currency, count(*) AS facts
            FROM financial_facts ff
            JOIN company_listings cl ON cl.company_id = ff.company_id
            WHERE ff.currency IS NOT NULL AND ff.currency <> 'USD'
            GROUP BY 1, 2
            ORDER BY 3 DESC
            LIMIT %s
            """,
            (limit,),
        )
        return [
            (row["ticker"], row["currency"], row["facts"]) for row in cur.fetchall()
        ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args(argv)

    with get_connection() as conn:
        if args.backfill:
            print(f"Backfilled currency on {_backfill(conn)} facts")
        print("Unit distribution (3-letter fiat units and per-share):")
        for unit, facts, companies in _distribution(conn):
            print(f"  {unit:10} {facts:>12,} facts  {companies:>6,} companies")
        print(f"\nTop {args.top} non-USD tickers:")
        for ticker, currency, facts in _top_companies(conn, args.top):
            print(f"  {ticker:8} {currency} {facts:>10,} facts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
