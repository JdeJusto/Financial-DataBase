-- 0023_equity_nci_alias.sql
-- Map StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest
-- to stockholders_equity for US-GAAP and IFRS filers.
--
-- 37 large caps (JNJ, CAT, T, VZ, CSX, ADM, PG, ...) only report this tag
-- at their latest period_end; without the alias core_financials returned
-- NULL equity and VI could not resolve their effective year.
--
-- financial_facts is never altered by this migration.

BEGIN;

INSERT INTO concept_normalization
  (namespace, concept, field, normalized_concept, combine, notes)
VALUES
  ('us-gaap',
   'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
   'stockholders_equity', 'StockholdersEquity', NULL,
   'large caps: JNJ, CAT, T, VZ, CSX, ADM, PG; includes NCI'),
  ('ifrs-full',
   'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
   'stockholders_equity', 'StockholdersEquity', NULL,
   'IFRS equivalent; no facts yet, prepared for future')
ON CONFLICT (namespace, concept) DO NOTHING;

COMMIT;
