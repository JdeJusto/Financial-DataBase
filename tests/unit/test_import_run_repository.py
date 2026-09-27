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


def _repo_with_rows(rows):
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchall.return_value = rows
    conn.cursor.return_value.__enter__.return_value = cur
    return ImportRunRepository(conn), cur


def test_close_dangling_runs_filters_by_age_and_pipeline():
    rows = [
        {
            "id": "r1",
            "pipeline": "prices_update",
            "started_at": "2026-09-05 18:39",
            "age_hours": 520.91,
        },
        {
            "id": "r2",
            "pipeline": "sec_sync",
            "started_at": "2026-09-25 10:00",
            "age_hours": 7.2,
        },
    ]
    repo, cur = _repo_with_rows(rows)

    closed = repo.close_dangling_runs(max_age_hours=6, pipelines=["prices_update"])

    assert [row["id"] for row in closed] == ["r1", "r2"]
    assert closed[0]["age_hours"] == 520.91  # ages are reported for logging
    query, params = cur.execute.call_args[0]
    assert "status = 'running'" in query
    assert "started_at < NOW() - (%s * interval '1 hour')" in query
    assert "pipeline = ANY(%s)" in query
    assert "stale_running_closed_by_maintenance" in query
    # existing error context must be preserved, not overwritten
    assert "COALESCE(errors, '{}'::jsonb)" in query
    assert "'previous_status', 'running'" in query
    assert "RETURNING id, pipeline, started_at" in query
    assert params == (6.0, ["prices_update"])


def test_close_dangling_runs_defaults_to_every_pipeline_after_six_hours():
    repo, cur = _repo_with_rows([])

    closed = repo.close_dangling_runs()

    assert closed == []
    query, params = cur.execute.call_args[0]
    assert "pipeline = ANY(%s)" not in query
    assert params == (6.0,)
