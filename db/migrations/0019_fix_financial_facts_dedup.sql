-- 0019_fix_financial_facts_dedup.sql
-- Make financial_facts idempotent when filing_id is NULL.
--
-- Bulk ingestion processes company facts before filings are linked, so filing_id
-- is NULL for those facts. PostgreSQL treats NULLs as distinct within a unique
-- constraint, so the original UNIQUE constraint did not deduplicate facts on
-- re-runs. Recreate it with NULLS NOT DISTINCT so NULL filing_id dedupes too.

-- Remove existing duplicate rows (keep the earliest) before tightening the constraint.
WITH ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (
               PARTITION BY company_id, concept, period_start, period_end, filing_id, source_id
               ORDER BY created_at ASC, id ASC
           ) AS rn
    FROM financial_facts
)
DELETE FROM financial_facts
WHERE id IN (SELECT id FROM ranked WHERE rn > 1);

-- Drop and recreate the unique constraint with NULL-safe deduplication.
ALTER TABLE financial_facts
    DROP CONSTRAINT financial_facts_company_id_concept_period_start_period_end__key;

ALTER TABLE financial_facts
    ADD CONSTRAINT financial_facts_company_id_concept_period_start_period_end__key
    UNIQUE NULLS NOT DISTINCT (company_id, concept, period_start, period_end, filing_id, source_id);
