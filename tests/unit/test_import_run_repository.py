"""Tests for ImportRunRepository (import_runs provenance repository)."""

from unittest.mock import MagicMock

from financial_database.db.repositories import ImportRunRepository


def _repo_with_cursor(rowcount: int):
    conn = MagicMock()
    cur = MagicMock()
    cur.rowcount = rowcount
    conn.cursor.return_value.__enter__.return_value = cur
    return ImportRunRepository(conn), cur


def test_mark_dangling_running_with_pipelines_filters_by_pipeline():
    repo, cur = _repo_with_cursor(rowcount=7)

    updated = repo.mark_dangling_running("provider-1", ["sec_sync", "sec_universe"])

    assert updated == 7
    query, params = cur.execute.call_args[0]
    assert "UPDATE import_runs" in query
    assert "WHERE provider_id = %s AND status = 'running'" in query
    assert "pipeline = ANY(%s)" in query
    assert "finished_at = NOW()" in query
    assert params == ("provider-1", ["sec_sync", "sec_universe"])


def test_mark_dangling_running_without_pipelines_closes_all_running():
    repo, cur = _repo_with_cursor(rowcount=0)

    updated = repo.mark_dangling_running("provider-1")

    assert updated == 0
    query, params = cur.execute.call_args[0]
    assert "pipeline = ANY(%s)" not in query
    assert params == ("provider-1",)