"""Load historical S&P 500 membership into ``sp500_constituents``.

Source: fja05680/sp500 (``sp500_ticker_start_end.csv``), a community-maintained
reconstruction of the index composition since 1996. Each row is a half-open
interval ``[start_date, end_date)``; ``end_date`` is empty for current members.

The source only knows tickers, not companies. Rows are matched to
``company_listings`` where possible; delisted constituents without an SEC
ticker stay with ``company_id = NULL`` and are reported as unresolved.

Usage:
    python -m scripts.load_sp500_historical
    python -m scripts.load_sp500_historical --file /tmp/sp500_ticker_start_end.csv
    python -m scripts.load_sp500_historical --sanity-check
    python -m scripts.load_sp500_historical --dry-run
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import urllib.request
from datetime import UTC, date, datetime

from financial_database.db.connection import get_connection

SOURCE_URL = (
    "https://raw.githubusercontent.com/fja05680/sp500/master/sp500_ticker_start_end.csv"
)
SOURCE_LABEL = "fja05680"
MIN_MEMBERS = 450
MAX_MEMBERS = 520


def normalize_ticker(raw: str) -> str:
    """Normalize a ticker to the Yahoo/SEC convention used in FDB.

    ``BRK.B`` -> ``BRK-B``; whitespace and surrounding quotes are removed.
    """
    return raw.strip().strip('"').upper().replace(".", "-")


def parse_constituents_csv(text: str) -> list[dict]:
    """Parse the fja05680 intervals CSV into normalized rows.

    Returns a list of ``{"ticker", "start_date", "end_date"}`` sorted by start
    date. Duplicate ``(ticker, start_date)`` rows keep the widest interval.
    """
    reader = csv.DictReader(io.StringIO(text))
    required = {"ticker", "start_date", "end_date"}
    if not required.issubset(
        {(field or "").strip() for field in reader.fieldnames or []}
    ):
        raise ValueError(
            f"unexpected CSV header: {reader.fieldnames!r}; expected {sorted(required)}"
        )

    rows: dict[tuple[str, date], dict] = {}
    for raw in reader:
        ticker = normalize_ticker(raw.get("ticker") or "")
        start_raw = (raw.get("start_date") or "").strip()
        if not ticker or not start_raw:
            continue
        start = date.fromisoformat(start_raw)
        end_raw = (raw.get("end_date") or "").strip()
        end = date.fromisoformat(end_raw) if end_raw else None
        if end is not None and end <= start:
            continue
        key = (ticker, start)
        existing = rows.get(key)
        if existing is None or _interval_length(end) > _interval_length(
            existing["end_date"]
        ):
            rows[key] = {"ticker": ticker, "start_date": start, "end_date": end}

    return sorted(rows.values(), key=lambda row: (row["start_date"], row["ticker"]))


def _interval_length(end: date | None) -> float:
    """Sort key that treats an open interval as the widest possible one."""
    return float("inf") if end is None else end.toordinal()


def members_at(rows: list[dict], as_of: date) -> set[str]:
    """Return the tickers that were index members on ``as_of``."""
    return {
        row["ticker"]
        for row in rows
        if row["start_date"] <= as_of
        and (row["end_date"] is None or row["end_date"] > as_of)
    }


def sanity_report(rows: list[dict], as_of: date) -> tuple[bool, str]:
    """Check that the snapshot on ``as_of`` looks like an S&P 500."""
    members = members_at(rows, as_of)
    count = len(members)
    ok = MIN_MEMBERS <= count <= MAX_MEMBERS
    return (
        ok,
        f"{as_of.isoformat()}: {count} members (expected {MIN_MEMBERS}-{MAX_MEMBERS})",
    )


def fetch_source(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read().decode("utf-8")


def resolve_company_ids(conn, tickers: list[str]) -> dict[str, str]:
    """Map ticker -> company_id using the primary listing, then any listing."""
    if not tickers:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT UPPER(ticker) AS ticker, company_id::text AS company_id
            FROM (
                SELECT DISTINCT ON (UPPER(ticker))
                    UPPER(ticker) AS ticker, company_id
                FROM company_listings
                WHERE UPPER(ticker) = ANY(%s)
                ORDER BY UPPER(ticker), is_active DESC, is_primary DESC, listing_date DESC NULLS LAST
            ) AS ranked
            """,
            (tickers,),
        )
        return {row["ticker"]: row["company_id"] for row in cur.fetchall()}


def load(
    conn,
    rows: list[dict],
    *,
    source: str = SOURCE_LABEL,
    replace: bool = True,
) -> dict:
    """Insert membership intervals and return load statistics."""
    tickers = sorted({row["ticker"] for row in rows})
    mapping = resolve_company_ids(conn, tickers)

    with conn.cursor() as cur:
        if replace:
            cur.execute("DELETE FROM sp500_constituents WHERE source = %s", (source,))
        cur.executemany(
            """
            INSERT INTO sp500_constituents
                (ticker, start_date, end_date, company_id, source)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (ticker, start_date) DO UPDATE
            SET end_date = EXCLUDED.end_date,
                company_id = EXCLUDED.company_id,
                source = EXCLUDED.source,
                loaded_at = now()
            """,
            [
                (
                    row["ticker"],
                    row["start_date"],
                    row["end_date"],
                    mapping.get(row["ticker"]),
                    source,
                )
                for row in rows
            ],
        )
    conn.commit()

    resolved = sum(1 for row in rows if mapping.get(row["ticker"]))
    return {
        "rows": len(rows),
        "tickers": len(tickers),
        "resolved": resolved,
        "unresolved": len(rows) - resolved,
        "first_date": min(row["start_date"] for row in rows) if rows else None,
        "last_date": max((row["end_date"] or row["start_date"]) for row in rows)
        if rows
        else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", help="local CSV (default: download from GitHub)")
    parser.add_argument("--url", default=SOURCE_URL, help="source URL")
    parser.add_argument("--source", default=SOURCE_LABEL, help="source label to store")
    parser.add_argument(
        "--sanity-check", action="store_true", help="print yearly member counts"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="parse and report without writing"
    )
    args = parser.parse_args(argv)

    if args.file:
        with open(args.file, encoding="utf-8") as handle:
            text = handle.read()
    else:
        text = fetch_source(args.url)
    rows = parse_constituents_csv(text)
    if not rows:
        print("No rows parsed from the source", file=sys.stderr)
        return 2

    if args.sanity_check:
        years = sorted(
            {row["start_date"].year for row in rows}
            | {datetime.now(tz=UTC).date().year}
        )
        failures = 0
        for year in years:
            ok, message = sanity_report(rows, date(year, 12, 31))
            print(("OK   " if ok else "WARN ") + message)
            failures += 0 if ok else 1
        print(f"{failures} year(s) outside the expected range")

    stats = {
        "rows": len(rows),
        "tickers": len({row["ticker"] for row in rows}),
    }
    if args.dry_run:
        print(f"Dry run: {stats['rows']} intervals, {stats['tickers']} tickers")
        return 0

    conn = get_connection()
    try:
        result = load(conn, rows, source=args.source)
    finally:
        conn.close()

    print(
        f"Loaded {result['rows']} intervals for {result['tickers']} tickers "
        f"({result['first_date']} -> {result['last_date']})"
    )
    print(
        f"Resolved company_id: {result['resolved']}/{result['rows']} intervals; "
        f"{result['unresolved']} without a matching listing (delisted/no SEC data)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
