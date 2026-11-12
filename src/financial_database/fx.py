"""Historical FX rates for currency-normalized fundamentals (v0.3.0).

The source of truth is the ECB euro reference rates (EUR base, daily). A
currency ``X`` is converted to USD with::

    usd_per_unit(X) = usd_per_eur / x_per_eur

For currencies the ECB does not publish, :func:`fetch_yfinance_series` provides
a fallback from Yahoo (``XUSD=X``, inverted when only ``USDX=X`` exists). A
missing rate never becomes 1.0: the fact's ``value_usd`` is left NULL and the
conversion is visible as unavailable.

Rates are stored in the ``fx_rates`` table by the loader script; the
``core_financials`` materialized view joins the latest rate on or before each
fact's ``period_end``, so weekends/holidays use the previous business day.
"""

from __future__ import annotations

import csv
import io
import os
import urllib.request
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta

ECB_BASE = "https://data-api.ecb.europa.eu/service/data/EXR/D.{currency}.EUR.SP00.A"
USER_AGENT = os.getenv(
    "FDB_USER_AGENT",
    "financial-database/0.3.0 (currency normalization; contact: local)",
)

#: Fiat currencies seen in SEC filings. Crypto, metals and indexed units
#: (ETH, BTC, XAU, XUA, CLF, UYI, ...) are deliberately excluded: they are not
#: converted by this pipeline and their ``currency`` stays NULL.
SUPPORTED_CURRENCIES: tuple[str, ...] = (
    "AED",
    "AFN",
    "ARS",
    "AUD",
    "BMD",
    "BRL",
    "BSD",
    "BWP",
    "CAD",
    "CHE",
    "CHF",
    "CLF",
    "CLP",
    "CNY",
    "COP",
    "CRC",
    "CUP",
    "CZK",
    "DKK",
    "DZD",
    "EUR",
    "GBP",
    "GEL",
    "GHS",
    "HKD",
    "HNL",
    "IDR",
    "ILS",
    "INR",
    "ISK",
    "JOD",
    "JPY",
    "KHR",
    "KPW",
    "KRW",
    "KZT",
    "MMK",
    "MOP",
    "MXN",
    "MYR",
    "NIO",
    "NIS",
    "NOK",
    "NZD",
    "PEN",
    "PHP",
    "PKR",
    "PLN",
    "RUB",
    "SAR",
    "SDG",
    "SEK",
    "SGD",
    "STD",
    "THB",
    "TJS",
    "TND",
    "TRY",
    "TWD",
    "TZS",
    "UAH",
    "USD",
    "UYI",
    "VEF",
    "VND",
    "ZAR",
)

#: Currencies the ECB publishes (EUR base); the rest need the Yahoo fallback.
#: Legacy/renamed ISO codes that Yahoo publishes under a newer code.
_YF_ALIASES = {"NIS": "ILS", "STD": "STN", "VEF": "VES"}

ECB_CURRENCIES: frozenset[str] = frozenset(
    {
        "AUD",
        "BRL",
        "CAD",
        "CHF",
        "CNY",
        "CZK",
        "DKK",
        "GBP",
        "HKD",
        "HUF",
        "IDR",
        "ILS",
        "INR",
        "ISK",
        "JPY",
        "KRW",
        "MXN",
        "MYR",
        "NOK",
        "NZD",
        "PHP",
        "PLN",
        "RON",
        "SEK",
        "SGD",
        "THB",
        "TRY",
        "USD",
        "ZAR",
    }
)


def currency_from_unit(unit: str | None) -> str | None:
    """Return the ISO currency encoded in a fact unit, or ``None``.

    ``EUR`` and ``EUR/shares`` both mean EUR; ``shares``, ``pure``, ``segment``
    and crypto/metal units do not map to a fiat currency.
    """
    if not unit:
        return None
    code = str(unit).strip().upper()
    if "/" in code:
        code = code.split("/", 1)[0]
    return code if code in SUPPORTED_CURRENCIES else None


def _request(url: str, timeout: float = 45.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def parse_ecb_csv(payload: str) -> dict[date, float]:
    """Parse an ECB ``csvdata`` response into ``{date: rate}``."""
    rates: dict[date, float] = {}
    reader = csv.DictReader(io.StringIO(payload))
    for row in reader:
        period = (row.get("TIME_PERIOD") or "").strip()
        value = (row.get("OBS_VALUE") or "").strip()
        if not period or not value:
            continue
        try:
            rates[date.fromisoformat(period)] = float(value)
        except (TypeError, ValueError):
            continue
    return rates


def fetch_ecb_series(
    currency: str,
    start: date,
    end: date,
    *,
    timeout: float = 45.0,
) -> dict[date, float]:
    """Fetch one ECB daily series (``currency`` per EUR)."""
    url = (
        ECB_BASE.format(currency=currency)
        + f"?startPeriod={start.isoformat()}&endPeriod={end.isoformat()}"
        + "&format=csvdata"
    )
    return parse_ecb_csv(_request(url, timeout=timeout))


def usd_per_unit_from_eur(
    currency: str,
    currency_per_eur: dict[date, float],
    usd_per_eur: dict[date, float],
) -> dict[date, float]:
    """Convert an ECB ``X per EUR`` series into ``USD per X``.

    ``USD`` returns the USD-per-EUR series unchanged; ``EUR`` is the same
    series. A zero/missing denominator is skipped, never treated as 1.0.
    """
    if currency in {"USD", "EUR"}:
        return dict(usd_per_eur)
    rates: dict[date, float] = {}
    for day, per_eur in currency_per_eur.items():
        usd = usd_per_eur.get(day)
        if usd is None or per_eur <= 0:
            continue
        rates[day] = usd / per_eur
    return rates


def fetch_yfinance_series(
    currency: str,
    start: date,
    end: date,
) -> dict[date, float]:
    """Yahoo fallback for currencies the ECB does not publish.

    Tries ``<CCY>USD=X`` first and ``USD<CCY>=X`` (inverted) second. Returns
    an empty mapping on failure; callers must not invent a 1.0 rate.
    """
    try:
        import yfinance as yf
    except Exception:  # noqa: BLE001 — optional extra not installed
        return {}
    # yfinance's end date is exclusive; add one day to include ``end``.
    exclusive_end = end + timedelta(days=1)
    symbol_currency = _YF_ALIASES.get(currency, currency)
    for symbol, invert in (
        (f"{symbol_currency}USD=X", False),
        (f"USD{symbol_currency}=X", True),
    ):
        try:
            frame = yf.Ticker(symbol).history(
                start=start, end=exclusive_end, auto_adjust=False
            )
        except Exception:  # noqa: BLE001, S112 — one failed pair must not stop the rest
            continue
        if frame is None or frame.empty or "Close" not in frame:
            continue
        rates: dict[date, float] = {}
        for index, row in frame.iterrows():
            try:
                day = (
                    index.date()
                    if hasattr(index, "date")
                    else date.fromisoformat(str(index)[:10])
                )
                close = float(row["Close"])
            except (TypeError, ValueError, AttributeError):
                continue
            if close <= 0:
                continue
            rates[day] = 1.0 / close if invert else close
        if rates:
            return rates
    return {}


def upsert_rates(
    conn, currency: str, rates: Iterable[tuple[date, float]], source: str
) -> int:
    """Insert/update ``fx_rates`` rows and return the number written."""
    rows = [(currency, day, float(rate), source) for day, rate in rates]
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO fx_rates (currency, rate_date, usd_per_unit, source)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (currency, rate_date) DO UPDATE
              SET usd_per_unit = EXCLUDED.usd_per_unit,
                  source = EXCLUDED.source
            """,
            rows,
        )
    conn.commit()
    return len(rows)


def today_utc() -> date:
    return datetime.now(UTC).date()
