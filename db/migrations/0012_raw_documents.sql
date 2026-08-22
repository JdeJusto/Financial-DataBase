-- 0012_raw_documents.sql
-- Metadata references to preserved raw data files.
-- Actual files stored in filesystem/object storage, PostgreSQL stores metadata only.

CREATE TABLE raw_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES data_providers(id) ON DELETE RESTRICT,
    source_identifier VARCHAR(255) NOT NULL, -- e.g., SEC accession number, API response ID
    storage_path VARCHAR(500) NOT NULL, -- filesystem path or object key
    checksum VARCHAR(64), -- SHA256 hex
    content_type VARCHAR(100),
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    is_processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider_id, source_identifier)
);

CREATE INDEX idx_raw_documents_provider ON raw_documents(provider_id);
CREATE INDEX idx_raw_documents_processed ON raw_documents(is_processed);
CREATE INDEX idx_raw_documents_retrieved ON raw_documents(retrieved_at);

COMMENT ON TABLE raw_documents IS 'Metadata for raw data files. Actual files in filesystem/S3. storage_path = path or object key.';