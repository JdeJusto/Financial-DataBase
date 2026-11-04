"""Unit test for the post-ingest core_financials refresh."""

from __future__ import annotations

from financial_database.db.refresh import refresh_core_financials


class _Cursor:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql):
        self.statements.append(sql)


class _Conn:
    def __init__(self):
        self._cursor = _Cursor()
        self.committed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True


def test_refresh_core_financials_uses_concurrent_refresh():
    conn = _Conn()

    refresh_core_financials(conn)

    assert conn._cursor.statements == [
        "REFRESH MATERIALIZED VIEW CONCURRENTLY core_financials"
    ]
    assert conn.committed is True
