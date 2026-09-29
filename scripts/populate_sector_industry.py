"""Populate ``companies.sector`` / ``companies.industry`` from Yahoo Finance.

Runtime data enrichment: the values written to the database are never
committed to git (the ``data_quality`` / ``analysis`` layers only read them).
Only ``companies.sector`` / ``companies.industry`` / ``updated_at`` are
touched — no prices, no listings, no identifiers.

The tool is **resumable by design**:

* in the default mode it only looks at companies whose ``sector`` is still
  NULL, so an interrupted run continues where it stopped;
* a checkpoint file (JSON, see ``--checkpoint``) additionally remembers
  tickers Yahoo could not resolve, so they are not retried on every run.

A Yahoo availability preflight (cookie -> crumb -> quote, i.e. the same path
``yfinance`` walks) aborts the run with a clear reason when Yahoo is
throttling, mirroring the probe used by Value Investing's price pipeline.

Usage::

    python -m scripts.populate_sector_industry                       # next batch
    python -m scripts.populate_sector_industry --limit 50
    python -m scripts.populate_sector_industry --tickers AAPL,MSFT,KO,PG,TSLA,JPM,BAC,PLD,O

Exit code is non-zero only when the run cannot reach the database or Yahoo;
companies that resolve no sector/industry are reported and skipped, never
fabricated.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import psycopg
import yfinance as yf

from financial_database.db.connection import get_connection

logger = logging.getLogger("populate_sector_industry")

#: Exchange codes whose listings map directly to Yahoo Finance symbols (see
#: ``financial_database/providers/price/yfinance_client.py::get_symbol``).
US_EXCHANGE_CODES = {
    "NYSE",
    "NASDAQ",
    "AMEX",
    "ARCA",
    "BATS",
    "NYSEAMERICAN",
    "NYSEARCA",
}

YAHOO_COOKIE_URL = "https://fc.yahoo.com"
YAHOO_CRUMB_URL = "https://query1.finance.yahoo.com/v1/test/getcrumb"
YAHOO_CHART_URL = (
    "https://query2.finance.yahoo.com/v8/finance/chart/AAPL?range=1d&interval=1d"
)

DEFAULT_CHECKPOINT = Path(
    os.environ.get("FDB_SECTOR_CHECKPOINT", "/tmp/fdb_sector_populate_checkpoint.json")
)


# ---------------------------------------------------------------------------
# Yahoo availability preflight
# ---------------------------------------------------------------------------
def yahoo_preflight(timeout: float = 10.0, attempts: int = 3) -> str:
    """Walk the same path yfinance walks; return '' when green, else a reason.

    Stages mirror Value Investing's ``backend/services/yahoo_health.py``: the
    cookie fetch is non-critical in yfinance (reported, not fatal), the crumb
    fetch is the fragile step (HTTP 429 -> throttle), and the quote fetch
    proves query2 answers with a crumb present.

    Each stage gets a bounded retry (``attempts``, 2s/4s apart) so a transient
    DNS or connection blip does not abort a long batch; persistent throttling
    (HTTP 429/401) still fails with the stage's reason.
    """
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookie_jar),
        urllib.request.HTTPRedirectHandler(),
    )
    # A minimal, plain UA: measured from this host, a browser-like UA without a
    # cookie/crumb session is what bot detection fingerprints and gets HTTP 429,
    # while a bare "Mozilla/5.0" answers 200 (see Value Investing
    # ``backend/services/yahoo_health.py``).
    opener.addheaders = [("User-Agent", "Mozilla/5.0")]

    def _open_with_retry(url: str):
        """(response, last_error): open with bounded retries, 2s/4s backoff."""
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                return opener.open(url, timeout=timeout), None
            except Exception as exc:  # noqa: BLE001 — classified by the caller
                last_error = exc
                if attempt + 1 < attempts:
                    time.sleep(2.0 * (attempt + 1))
        return None, last_error

    _, error = _open_with_retry(YAHOO_COOKIE_URL)
    if error is not None:
        logger.info("preflight cookie step failed (non-critical): %s", error)
    response, error = _open_with_retry(YAHOO_CRUMB_URL)
    if error is not None:
        if isinstance(error, urllib.error.HTTPError):
            return f"crumb step HTTP {error.code} (Yahoo throttling or refusing)"
        return f"crumb step {type(error).__name__}: {error}"
    with response:
        crumb = response.read().decode("utf-8", "replace").strip()
    if not crumb:
        return "crumb step returned an empty crumb (looks like a 401 wall)"
    _, error = _open_with_retry(YAHOO_CHART_URL)
    if error is not None:
        if isinstance(error, urllib.error.HTTPError):
            return f"quote step HTTP {error.code}"
        return f"quote step {type(error).__name__}: {error}"
    return ""


# ---------------------------------------------------------------------------
# Target selection
# ---------------------------------------------------------------------------
def _fetch_targets(
    conn: psycopg.Connection,
    tickers: list[str] | None,
    limit: int | None,
    exclude: set[str] | None = None,
) -> list[dict]:
    """Companies to enrich, most diverse first.

    * ``tickers`` set — resolve those symbols through ``company_listings``
      (preferring active/primary listings); no exchange filter.
    * ``tickers`` empty — companies whose ``sector`` is NULL with a resolvable
      US exchange listing, excluding ``exclude`` (the checkpoint's attempted
      tickers) *before* ``limit`` is applied: otherwise a bounded run keeps
      returning the same already-attempted no-data companies and never
      advances.
    """
    excluded = sorted(exclude or ())
    with conn.cursor() as cur:
        if tickers:
            cur.execute(
                """
                SELECT DISTINCT ON (c.id)
                       c.id AS company_id,
                       cl.ticker,
                       c.legal_name
                FROM companies c
                JOIN company_listings cl ON cl.company_id = c.id AND cl.is_active
                WHERE UPPER(cl.ticker) = ANY(%s)
                ORDER BY c.id, cl.is_primary DESC NULLS LAST, cl.ticker
                """,
                ([t.upper() for t in tickers],),
            )
        else:
            sql = """
                SELECT DISTINCT ON (c.id)
                       c.id AS company_id,
                       cl.ticker,
                       c.legal_name
                FROM companies c
                JOIN company_listings cl ON cl.company_id = c.id AND cl.is_active
                JOIN exchanges e ON e.id = cl.exchange_id
                WHERE c.sector IS NULL
                  AND UPPER(e.code) = ANY(%s)
                  AND UPPER(cl.ticker) <> ALL(%s)
                ORDER BY c.id, cl.is_primary DESC NULLS LAST, cl.ticker
            """
            params: list = [sorted(US_EXCHANGE_CODES), excluded]
            if limit is not None:
                sql += " LIMIT %s"
                params.append(int(limit))
            cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Checkpoint (resume across runs)
# ---------------------------------------------------------------------------
def _load_checkpoint(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text())
        return {str(t).upper() for t in data.get("attempted", [])}
    except Exception:  # noqa: BLE001 — a corrupt checkpoint must not abort
        logger.warning("ignoring unreadable checkpoint %s", path)
        return set()


def _save_checkpoint(path: Path, attempted: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"attempted": sorted(attempted)}, indent=2))


# ---------------------------------------------------------------------------
# Yahoo per-ticker enrichment
# ---------------------------------------------------------------------------
def _fetch_sector_info(ticker: str) -> dict:
    """Yahoo quote/quoteSummary info for a symbol, retried on transient errors."""
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            info = yf.Ticker(ticker).info or {}
            if info:
                return info
        except Exception as exc:  # noqa: BLE001 — network/rate-limit noise
            last_error = exc
        time.sleep(0.5 + attempt)
    if last_error is not None:
        raise last_error
    return {}


def _update_company(
    conn: psycopg.Connection, company_id: str, sector: str | None, industry: str | None
) -> None:
    """Set sector/industry only when found; never clears what is known."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE companies
            SET sector = COALESCE(%s, sector),
                industry = COALESCE(%s, industry),
                updated_at = NOW()
            WHERE id = %s
            """,
            (sector, industry, company_id),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--tickers",
        help="comma-separated symbols to enrich (default: next batch of NULL-sector companies)",
    )
    parser.add_argument("--limit", type=int, help="max companies when no --tickers")
    parser.add_argument(
        "--sleep", type=float, default=0.3, help="seconds between Yahoo calls"
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=DEFAULT_CHECKPOINT,
        help="resume checkpoint file (default: %(default)s)",
    )
    parser.add_argument(
        "--ignore-checkpoint",
        action="store_true",
        help="re-attempt tickers already recorded in the checkpoint",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    tickers = (
        [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        if args.tickers
        else None
    )
    if tickers:
        print(f"targets: {len(tickers)} explicit ticker(s)")
    else:
        scope = f" up to {args.limit}" if args.limit else ""
        print(f"targets: next batch of companies without a sector{scope}")

    reason = yahoo_preflight()
    if reason:
        print(
            f"ABORT: Yahoo preflight failed ({reason}). Retry later.", file=sys.stderr
        )
        return 2

    try:
        conn = get_connection()
    except Exception as exc:  # noqa: BLE001 — fail fast with a clear message
        print(f"ABORT: cannot connect to the database: {exc}", file=sys.stderr)
        return 3

    attempted = set() if args.ignore_checkpoint else _load_checkpoint(args.checkpoint)
    if tickers and not args.ignore_checkpoint:
        attempted -= set(tickers)  # explicit tickers always get another chance

    targets = _fetch_targets(conn, tickers, args.limit, exclude=attempted)
    print(
        f"candidates: {len(targets)} (checkpoint already holds {len(attempted)} ticker(s))"
    )

    populated = 0
    skipped = 0
    errors = 0
    for row in targets:
        ticker = row["ticker"].upper()
        if ticker in attempted:
            continue
        try:
            info = _fetch_sector_info(ticker)
            sector = info.get("sector")
            industry = info.get("industry")
            if sector is None and industry is None:
                print(f"{ticker:<8} {row['legal_name']:<48} no-data      (skipped)")
                skipped += 1
            else:
                _update_company(conn, row["company_id"], sector, industry)
                print(
                    f"{ticker:<8} {row['legal_name']:<48} "
                    f"{sector or '-':<24} {industry or '-'}"
                )
                populated += 1
        except Exception as exc:  # noqa: BLE001 — one bad ticker must not stop the batch
            print(
                f"{ticker:<8} {row['legal_name']:<48} ERROR  {type(exc).__name__}: {exc}"
            )
            errors += 1
        attempted.add(ticker)
        _save_checkpoint(args.checkpoint, attempted)
        time.sleep(args.sleep)

    print(
        f"done: {populated} populated, {skipped} no sector info, {errors} errors, "
        f"{len(targets) - populated - skipped - errors} skipped via checkpoint"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
