"""Unit tests for the historical S&P 500 membership loader."""

from __future__ import annotations

from datetime import date

import pytest

from scripts.load_sp500_historical import (
    members_at,
    normalize_ticker,
    parse_constituents_csv,
    sanity_report,
)

CSV = """ticker,start_date,end_date
AAPL,1982-11-30,
BRK.B,1996-01-02,
ENRN,1996-01-02,2001-11-30
ENRN,2001-12-01,
AAPL,1982-11-30,1990-01-01
"""


def test_normalize_ticker_handles_class_shares():
    assert normalize_ticker(" brk.b ") == "BRK-B"
    assert normalize_ticker("AAPL") == "AAPL"


def test_parse_keeps_widest_duplicate_interval():
    rows = parse_constituents_csv(CSV)
    apple = [row for row in rows if row["ticker"] == "AAPL"]
    assert len(apple) == 1
    assert apple[0]["start_date"] == date(1982, 11, 30)
    assert apple[0]["end_date"] is None


def test_parse_accepts_multiple_non_overlapping_intervals():
    rows = parse_constituents_csv(CSV)
    enron = [row for row in rows if row["ticker"] == "ENRN"]
    assert [row["start_date"] for row in enron] == [date(1996, 1, 2), date(2001, 12, 1)]


def test_parse_rejects_invalid_intervals():
    rows = parse_constituents_csv(
        "ticker,start_date,end_date\nX,2020-01-01,2020-01-01\n"
    )
    assert rows == []


def test_parse_rejects_missing_columns():
    with pytest.raises(ValueError):
        parse_constituents_csv("ticker,start\nAAPL,1982-11-30\n")


def test_members_at_is_half_open():
    rows = parse_constituents_csv(CSV)
    assert "ENRN" in members_at(rows, date(2001, 11, 29))
    assert "ENRN" not in members_at(rows, date(2001, 11, 30))
    assert "AAPL" in members_at(rows, date(2024, 12, 31))


def test_sanity_report_flags_implausible_counts():
    rows = parse_constituents_csv(
        "ticker,start_date,end_date\n"
        + "\n".join(f"T{i},2020-01-01," for i in range(3))
    )
    ok, message = sanity_report(rows, date(2020, 12, 31))
    assert not ok
    assert "3 members" in message
