-- 0020_extend_financial_facts_columns.sql
-- Extend string columns in financial_facts to accommodate longer SEC XBRL values
-- SEC XBRL data can contain frames, namespaces, and source IDs exceeding 255 chars

ALTER TABLE financial_facts
    ALTER COLUMN concept TYPE TEXT,
    ALTER COLUMN source_id TYPE TEXT,
    ALTER COLUMN namespace TYPE TEXT,
    ALTER COLUMN frame TYPE TEXT,
    ALTER COLUMN unit TYPE VARCHAR(200),
    ALTER COLUMN form TYPE VARCHAR(100),
    ALTER COLUMN fiscal_period TYPE VARCHAR(50);