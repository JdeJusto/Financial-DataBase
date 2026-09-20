#!/usr/bin/env python3
"""Regenerate the section-4 ticker snapshot inside check_ticker_health.sql.

Section 4 of scripts/check_ticker_health.sql embeds the Value Investing
universe (config/universe.csv) as a VALUES list so the health check can
report universe tickers that do not resolve to a CIK in this database.
This script rewrites that block from the current universe.csv so the
snapshot stays in sync.

Usage:
    .venv/bin/python docs/dev/rebuild_health_universe.py

The script locates the script file relative to this repository, replaces
the VALUES list between section 4's "(VALUES" marker and the closing ")"
line, and rewrites the file in place. It fails loudly if the universe file
or the marker lines cannot be found.
"""

from __future__ import annotations

import csv
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HEALTH_SCRIPT = os.path.join(REPO_ROOT, "scripts", "check_ticker_health.sql")

# Value Investing universe file; override with UNIVERSE_CSV if the layout differs.
DEFAULT_UNIVERSE = os.path.join(
    os.path.dirname(REPO_ROOT), "Value_Investing", "config", "universe.csv"
)
UNIVERSE_CSV = os.environ.get("UNIVERSE_CSV", DEFAULT_UNIVERSE)

TICKERS_PER_LINE = 10


def _read_tickers(path: str) -> list[str]:
    if not os.path.exists(path):
        raise SystemExit(f"universe file not found: {path}")
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    tickers = [row["ticker"].strip() for row in rows if row["ticker"].strip()]
    if not tickers:
        raise SystemExit(f"no tickers read from {path}")
    return tickers


def _values_block(tickers: list[str]) -> str:
    lines = []
    for i in range(0, len(tickers), TICKERS_PER_LINE):
        chunk = tickers[i : i + TICKERS_PER_LINE]
        lines.append(
            "        " + ", ".join(f"('{t}')" for t in chunk) + ","
        )
    # Drop the trailing comma on the final row.
    return "\n".join(lines).rstrip()[:-1]


def main() -> None:
    tickers = _read_tickers(UNIVERSE_CSV)
    block = _values_block(tickers)

    with open(HEALTH_SCRIPT, encoding="utf-8") as fh:
        script = fh.read()

    start_marker = "WITH universe(ticker) AS (\n    VALUES\n"
    if start_marker not in script:
        raise SystemExit(
            f"section 4 VALUES marker not found in {HEALTH_SCRIPT}"
        )
    start = script.index(start_marker) + len(start_marker)
    end_marker = "\n)\n"
    end = script.index(end_marker, start)

    new_script = script[:start] + block + script[end:]
    with open(HEALTH_SCRIPT, "w", encoding="utf-8") as fh:
        fh.write(new_script)

    print(
        f"rewrote section 4 of {HEALTH_SCRIPT} with {len(tickers)} tickers "
        f"from {UNIVERSE_CSV}"
    )


if __name__ == "__main__":
    sys.exit(main())