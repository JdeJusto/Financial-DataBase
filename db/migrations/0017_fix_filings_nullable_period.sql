-- 0017_fix_filings_nullable_period.sql
-- Make period_end nullable in filings table to handle SEC filings without period_of_report
-- SEC submissions may not always provide period_of_report

ALTER TABLE filings
    ALTER COLUMN period_end DROP NOT NULL;

-- Add check constraint for period consistency (period_start <= period_end OR either is NULL)
-- The existing check constraint should be updated
ALTER TABLE filings
    DROP CONSTRAINT IF EXISTS chk_filings_period;

ALTER TABLE filings
    ADD CONSTRAINT chk_filings_period
    CHECK (period_start IS NULL OR period_end IS NULL OR period_start <= period_end);

COMMENT ON COLUMN filings.period_end IS 'End of reporting period. NULL when SEC does not provide period_of_report.';