-- Historical Coverage Verification
-- Confirms major SEC filers have XBRL data going back to ~2009-2010.
--
-- Run against financial_database after the stress test / full load.

WITH target(company_name, cik) AS (
    VALUES
        ('Apple Inc.',            '0000320193'),
        ('Microsoft Corp',        '0000789019'),
        ('NVIDIA Corp',           '0001045810'),
        ('Alphabet Inc.',         '0001652044'),
        ('Amazon.com Inc.',       '0001018724'),
        ('Meta Platforms Inc.',   '0001326801'),
        ('Tesla Inc.',            '0001318605'),
        ('JPMorgan Chase & Co.',  '0000019617'),
        ('Walmart Inc.',          '0000104169'),
        ('Coca-Cola Co.',         '0000021344'),
        ('McDonald''s Corp',      '0000063908'),
        ('Johnson & Johnson',     '0000200406'),
        ('Procter & Gamble Co.',  '0000080424'),
        ('Bank of America Corp',  '0000070858'),
        ('Chevron Corp',          '0000093410'),
        ('Home Depot Inc.',       '0000354950'),
        ('Intel Corp',            '0000050863'),
        ('Merck & Co. Inc.',      '0000310158'),
        ('Pfizer Inc.',           '0000078003'),
        ('Verizon Communications','0000732712'),
        ('Cisco Systems Inc.',    '0000858877'),
        ('Boeing Co.',            '0000012927'),
        ('Walt Disney Co.',       '0001744489')
)
SELECT
    t.company_name,
    t.cik,
    min(ff.fiscal_year)                                   AS earliest_fiscal_year,
    max(ff.fiscal_year)                                   AS latest_fiscal_year,
    count(DISTINCT ff.fiscal_year)                        AS distinct_fiscal_years,
    count(*)                                              AS total_facts
FROM target t
LEFT JOIN company_identifiers ci
       ON ci.identifier_type = 'CIK'
      AND ci.identifier_value = t.cik
LEFT JOIN financial_facts ff
       ON ff.company_id = ci.company_id
GROUP BY t.company_name, t.cik
ORDER BY t.company_name;
