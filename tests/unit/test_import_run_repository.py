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


def test_create_scopes_run_to_company_when_given():
    """Per-company pipelines record the company they ingested (migration
    0021); batch pipelines pass None."""
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchall.return_value = [
        {
            "id": "run-1",
            "provider_id": "p",
            "pipeline": "sec_sync",
            "status": "running",
            "company_id": "company-9",
        }
    ]
    conn.cursor.return_value.__enter__.return_value = cur
    repo = ImportRunRepository(conn)

    run = repo.create("p", "sec_sync", "running", company_id="company-9")

    query, params = cur.execute.call_args[0]
    assert "company_id" in query.split("VALUES")[0]
    assert params == ("p", "sec_sync", "running", "company-9")
    assert run["company_id"] == "company-9"


def test_create_leaves_company_null_for_batch_pipelines():
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchall.return_value = [{"id": "run-2", "company_id": None}]
    conn.cursor.return_value.__enter__.return_value = cur
    repo = ImportRunRepository(conn)

    repo.create("p", "sec_update_incremental", "running")

    _query, params = cur.execute.call_args[0]
    assert params == ("p", "sec_update_incremental", "running", None)


def test_get_latest_for_company_uses_the_company_index():
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchone.return_value = {
        "id": "run-9",
        "pipeline": "sec_sync",
        "status": "success",
        "company_id": "company-9",
    }
    conn.cursor.return_value.__enter__.return_value = cur
    repo = ImportRunRepository(conn)

    latest = repo.get_latest_for_company("company-9")

    assert latest["id"] == "run-9"
    query, params = cur.execute.call_args[0]
    assert "WHERE company_id = %s" in query
    assert "ORDER BY started_at DESC" in query
    assert params == ("company-9",)
