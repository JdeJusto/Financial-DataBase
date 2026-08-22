-- 0013_import_runs.sql
-- Import/ETL audit trail.

CREATE TABLE import_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES data_providers(id) ON DELETE RESTRICT,
    pipeline VARCHAR(100) NOT NULL, -- 'companies', 'filings', 'financial_facts', 'prices', etc.
    status VARCHAR(20) NOT NULL DEFAULT 'running', -- 'running', 'success', 'failed', 'partial'
    records_processed INTEGER DEFAULT 0,
    records_inserted INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    records_skipped INTEGER DEFAULT 0,
    errors JSONB DEFAULT '{}',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_import_runs_status CHECK (status IN ('running', 'success', 'failed', 'partial'))
);

CREATE INDEX idx_import_runs_provider ON import_runs(provider_id);
CREATE INDEX idx_import_runs_status ON import_runs(status);
CREATE INDEX idx_import_runs_started ON import_runs(started_at);

COMMENT ON TABLE import_runs IS 'ETL/import audit trail. Tracks provenance of data loading operations.';