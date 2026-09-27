-- 0021_import_runs_company_id.sql
-- Scope import runs to the company they target.
--
-- Until now an import run only knew its pipeline, so "was this company
-- synced recently?" had to be answered indirectly (max(financial_facts.
-- updated_at), max(filings.created_at), companies.updated_at) or from a
-- pipeline-wide "did anything succeed lately" query that could not be
-- attributed to a single company. Per-company runs (sec sync,
-- sec_submissions, sec_companyfacts) now record the company they ingested,
-- which makes per-company freshness a single indexed lookup. Batch-level
-- runs (sec_universe, update-incremental, sec_bulk_full_universe,
-- prices_update) keep NULL on purpose: they span many companies.

ALTER TABLE import_runs
    ADD COLUMN company_id UUID REFERENCES companies(id) ON DELETE SET NULL;

CREATE INDEX idx_import_runs_company_started
    ON import_runs (company_id, started_at DESC);

-- Serves the common "latest status per pipeline" lookups (health checks,
-- dashboards) without scanning finished runs.
CREATE INDEX idx_import_runs_pipeline_status_finished
    ON import_runs (pipeline, status, finished_at DESC);

COMMENT ON COLUMN import_runs.company_id IS
    'Company this import run targeted, when applicable (per-company syncs).';
