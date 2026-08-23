-- 0018_add_namespace_frame_to_financial_facts.sql
-- Add explicit namespace and frame columns to financial_facts for better provenance and analytics
-- Currently namespace is embedded in source_id, frame is not stored

ALTER TABLE financial_facts
    ADD COLUMN namespace VARCHAR(100); -- e.g., 'us-gaap', 'dei', 'invest'

ALTER TABLE financial_facts
    ADD COLUMN frame VARCHAR(50); -- SEC frame codes e.g., 'CY2023', 'CY2023Q1', 'CY2023Q2I'

-- Add index for namespace-based queries
CREATE INDEX idx_financial_facts_namespace ON financial_facts(namespace);

-- Add index for frame-based queries
CREATE INDEX idx_financial_facts_frame ON financial_facts(frame);

COMMENT ON COLUMN financial_facts.namespace IS 'XBRL namespace (us-gaap, dei, invest, etc.). Previously embedded in source_id.';
COMMENT ON COLUMN financial_facts.frame IS 'SEC frame code (e.g., CY2023, CY2023Q1, CY2023Q2I). Not previously stored.';