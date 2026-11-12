"""Unit tests for the FX/currency helpers (no database, no network)."""

from __future__ import annotations

from datetime import date

from financial_database.fx import (
    SUPPORTED_CURRENCIES,
    currency_from_unit,
    parse_ecb_csv,
    usd_per_unit_from_eur,
)

SAMPLE = """KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE
EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2024-12-20,1.039
EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2024-12-23,1.0393
EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2024-12-24,
"""


def test_currency_from_unit():
    assert currency_from_unit("EUR") == "EUR"
    assert currency_from_unit("GBP/shares") == "GBP"
    assert currency_from_unit("usd") == "USD"
    assert currency_from_unit("shares") is None
    assert currency_from_unit("pure") is None
    assert currency_from_unit("ETC") is None
    assert currency_from_unit(None) is None


def test_supported_currencies_are_three_letter_fiat_codes():
    assert "USD" in SUPPORTED_CURRENCIES
    assert "EUR" in SUPPORTED_CURRENCIES
    assert "GBP" in SUPPORTED_CURRENCIES
    assert "BTC" not in SUPPORTED_CURRENCIES
    assert "XAU" not in SUPPORTED_CURRENCIES
    assert all(len(code) == 3 and code.isupper() for code in SUPPORTED_CURRENCIES)


def test_parse_ecb_csv_skips_missing_values():
    rates = parse_ecb_csv(SAMPLE)
    assert rates == {
        date(2024, 12, 20): 1.039,
        date(2024, 12, 23): 1.0393,
    }


def test_usd_per_unit_from_eur_cross():
    usd_per_eur = {date(2024, 12, 20): 1.039, date(2024, 12, 23): 1.0393}
    gbp_per_eur = {date(2024, 12, 20): 0.82965, date(2024, 12, 23): 0.82995}

    rates = usd_per_unit_from_eur("GBP", gbp_per_eur, usd_per_eur)

    assert rates[date(2024, 12, 20)] == 1.039 / 0.82965
    assert rates[date(2024, 12, 23)] == 1.0393 / 0.82995


def test_usd_per_unit_from_eur_returns_usd_series_for_usd_and_eur():
    usd_per_eur = {date(2024, 12, 20): 1.039}
    assert usd_per_unit_from_eur("USD", {}, usd_per_eur) == usd_per_eur
    assert usd_per_unit_from_eur("EUR", {}, usd_per_eur) == usd_per_eur


def test_usd_per_unit_from_eur_skips_missing_and_zero_denominators():
    usd_per_eur = {date(2024, 12, 20): 1.039, date(2024, 12, 23): 1.04}
    gbp_per_eur = {date(2024, 12, 20): 0.0, date(2024, 12, 24): 0.83}

    assert usd_per_unit_from_eur("GBP", gbp_per_eur, usd_per_eur) == {}
