"""Unit tests for CompanyListingRepository query correctness."""

from financial_database.db.repositories.company_listing_repository import (
    CompanyListingRepository,
)


class _RecordingCursor:
    def __init__(self, capture):
        self._capture = capture

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self._capture["query"] = query

    def fetchall(self):
        return []


class _RecordingConnection:
    def __init__(self, capture):
        self._capture = capture

    def cursor(self):
        return _RecordingCursor(self._capture)


def test_get_by_company_id_uses_delisting_date():
    captured = {}
    repo = CompanyListingRepository(_RecordingConnection(captured))

    repo.get_by_company_id("company-uuid")

    assert "delisting_date" in captured["query"]
    assert "delisted_date" not in captured["query"]


def test_get_by_ticker_uses_delisting_date():
    captured = {}
    repo = CompanyListingRepository(_RecordingConnection(captured))

    repo.get_by_ticker("AAPL")

    assert "delisting_date" in captured["query"]
    assert "delisted_date" not in captured["query"]
