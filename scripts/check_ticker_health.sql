-- Ticker / CIK Health Check
-- Run against financial_database after any ticker->CIK mapping change.
--
-- Maps the mapping-defect classes that can let a ticker resolve to the
-- wrong (stub) entity. A healthy database returns few or no rows.
--
--   1. TRUE STUB companies: companies whose facts-bearing core accessions
--      (10-K/10-Q/20-F/40-F family) were all filed under a CIK that is
--      neither their own nor a professional EDGAR filing agent. SEC
--      accession numbers carry the CIK of the submitting entity: for most
--      companies that is a filing agent (Donnelley, Toppan Merrill,
--      Intelligize, ...), NOT the company itself, so a company is only a
--      stub when NONE of its core filings used its own CIK AND none used a
--      filing agent. A prefix CIK is treated as a filing agent when it
--      submits for more than 3 distinct companies (a parent or subsidiary
--      files only for a handful of related entities, so genuine
--      parent/subsidiary cross-filers like ENTERGY ARKANSAS stay visible).
--      Companies with zero core-form facts are not stubs: they surface in
--      section 3 when they have no facts at all, and otherwise are a
--      data-completeness concern.
--   2. MULTI-CIK: one active universe ticker mapped to multiple distinct CIKs.
--   3. ZERO-FACTS: an active universe ticker whose company has no facts.
--   4. UNIVERSE RESOLUTION: tickers in Value_Investing/config/universe.csv
--      that do not resolve to a company holding a CIK identifier here. The
--      embedded block is a snapshot of that file (500 tickers).
--   Regenerate this block after any universe.csv change by running:
--     .venv/bin/python scripts/dev/rebuild_health_universe.py
--   (reads Value Investing's config/universe.csv and rewrites this file).

\set ON_ERROR_STOP off

\echo '=== 1. TRUE STUB companies (core facts only from third-party/related-entity prefixes) ==='
WITH core_prefix_facts AS (
    SELECT f.company_id,
           left(f.accession_number, 10) AS prefix,
           count(*) AS facts
    FROM filings f
    JOIN financial_facts ff ON ff.filing_id = f.id
    WHERE f.form IN ('10-K','10-K/A','10-KT','10-KT/A','10-Q','10-Q/A','10-QT','10-QT/A',
                     '20-F','20-F/A','40-F','40-F/A')
    GROUP BY 1, 2
),
-- Professional EDGAR filing agents: prefixes that submit for more than 3
-- distinct companies. A parent or subsidiary files only for a handful of
-- related entities, so it stays below the threshold and remains visible.
agent_prefixes AS (
    SELECT prefix
    FROM core_prefix_facts
    GROUP BY prefix
    HAVING count(DISTINCT company_id) > 3
),
company_cik AS (
    SELECT ci.company_id, ci.identifier_value AS cik
    FROM company_identifiers ci
    WHERE ci.identifier_type = 'CIK'
),
-- Companies whose own CIK never appears as the prefix of their
-- facts-bearing core accessions.
no_own_prefix AS (
    SELECT DISTINCT c.id
    FROM companies c
    JOIN company_cik cik ON cik.company_id = c.id
    JOIN company_listings cl ON cl.company_id = c.id AND cl.is_active = TRUE
    WHERE NOT EXISTS (
        SELECT 1 FROM core_prefix_facts cpf
        WHERE cpf.company_id = c.id AND cpf.prefix = cik.cik
    )
)
SELECT c.legal_name,
       cik.cik AS company_cik,
       cl.ticker,
       sum(m.facts) AS n_core_facts,
       string_agg(DISTINCT m.prefix, ', ') AS filing_prefixes
FROM no_own_prefix n
JOIN companies c ON c.id = n.id
JOIN company_cik cik ON cik.company_id = c.id
JOIN company_listings cl ON cl.company_id = c.id AND cl.is_active = TRUE
JOIN core_prefix_facts m ON m.company_id = c.id
WHERE NOT EXISTS (
    -- exclude the company entirely when ANY of its core accessions went
    -- through a professional filing agent (benign agent-filed company)
    SELECT 1
    FROM core_prefix_facts cpf
    JOIN agent_prefixes ap ON ap.prefix = cpf.prefix
    WHERE cpf.company_id = c.id
)
GROUP BY c.legal_name, cik.cik, cl.ticker
ORDER BY cik.cik;

\echo '=== 2. Single active universe ticker mapped to multiple distinct CIKs ==='
SELECT cl.ticker,
       count(DISTINCT ci.identifier_value) AS n_ciks,
       string_agg(DISTINCT ci.identifier_value, ', ' ORDER BY ci.identifier_value) AS ciks,
       string_agg(DISTINCT c.legal_name, ' | ' ORDER BY c.legal_name) AS companies
FROM company_listings cl
JOIN companies c ON c.id = cl.company_id
JOIN company_identifiers ci
  ON ci.company_id = c.id
 AND ci.identifier_type = 'CIK'
WHERE cl.is_active = TRUE
GROUP BY cl.ticker
HAVING count(DISTINCT ci.identifier_value) > 1
ORDER BY cl.ticker;

\echo '=== 3. Active universe ticker with zero financial facts ==='
SELECT cl.ticker,
       c.legal_name,
       ci.identifier_value AS cik
FROM company_listings cl
JOIN companies c ON c.id = cl.company_id
LEFT JOIN company_identifiers ci
  ON ci.company_id = c.id
 AND ci.identifier_type = 'CIK'
WHERE cl.is_active = TRUE
  AND NOT EXISTS (SELECT 1 FROM financial_facts ff WHERE ff.company_id = c.id)
ORDER BY cl.ticker;

\echo '=== 4. Value Investing universe tickers without a CIK mapping in this database ==='
WITH universe(ticker) AS (
    VALUES
        ('A'), ('AAPL'), ('ABBV'), ('ABNB'), ('ABT'), ('ACGL'), ('ACN'), ('ADBE'), ('ADI'), ('ADM'),
        ('ADP'), ('ADSK'), ('AEE'), ('AEP'), ('AES'), ('AFL'), ('AIG'), ('AIZ'), ('AJG'), ('AKAM'),
        ('ALB'), ('ALGN'), ('ALL'), ('ALLE'), ('AMAT'), ('AMCR'), ('AMD'), ('AME'), ('AMGN'), ('AMP'),
        ('AMT'), ('AMZN'), ('ANET'), ('AON'), ('AOS'), ('APA'), ('APD'), ('APH'), ('APO'), ('APP'),
        ('APTV'), ('ARE'), ('ARES'), ('ATO'), ('AVGO'), ('AVY'), ('AWK'), ('AXON'), ('AXP'), ('AZO'),
        ('BA'), ('BAC'), ('BALL'), ('BAX'), ('BBY'), ('BDX'), ('BEN'), ('BF-B'), ('BG'), ('BIIB'),
        ('BKNG'), ('BKR'), ('BLDR'), ('BLK'), ('BMY'), ('BNY'), ('BR'), ('BRK-B'), ('BRO'), ('BSX'),
        ('BX'), ('BXP'), ('C'), ('CAH'), ('CARR'), ('CASY'), ('CAT'), ('CB'), ('CBOE'), ('CBRE'),
        ('CCI'), ('CCL'), ('CDNS'), ('CDW'), ('CEG'), ('CF'), ('CFG'), ('CHD'), ('CHRW'), ('CHTR'),
        ('CI'), ('CIEN'), ('CINF'), ('CL'), ('CLX'), ('CMCSA'), ('CME'), ('CMG'), ('CMI'), ('CMS'),
        ('CNC'), ('CNP'), ('COF'), ('COHR'), ('COIN'), ('COO'), ('COP'), ('COR'), ('COST'), ('CPAY'),
        ('CPRT'), ('CPT'), ('CRH'), ('CRL'), ('CRM'), ('CRWD'), ('CSCO'), ('CSGP'), ('CSX'), ('CTAS'),
        ('CTSH'), ('CTVA'), ('CVNA'), ('CVS'), ('CVX'), ('D'), ('DAL'), ('DASH'), ('DD'), ('DDOG'),
        ('DE'), ('DECK'), ('DELL'), ('DG'), ('DGX'), ('DHI'), ('DHR'), ('DIS'), ('DLR'), ('DLTR'),
        ('DOC'), ('DOV'), ('DOW'), ('DPZ'), ('DRI'), ('DTE'), ('DUK'), ('DVA'), ('DVN'), ('DXCM'),
        ('EBAY'), ('ECHO'), ('ECL'), ('ED'), ('EFX'), ('EG'), ('EIX'), ('EL'), ('ELV'), ('EME'),
        ('EMR'), ('EOG'), ('EQIX'), ('EQT'), ('ERIE'), ('ES'), ('ESS'), ('ETN'), ('ETR'), ('EVRG'),
        ('EW'), ('EXC'), ('EXE'), ('EXPD'), ('EXPE'), ('EXR'), ('F'), ('FANG'), ('FAST'), ('FCX'),
        ('FDS'), ('FDX'), ('FDXF'), ('FE'), ('FERG'), ('FFIV'), ('FICO'), ('FIS'), ('FISV'), ('FITB'),
        ('FIX'), ('FLEX'), ('FOXA'), ('FRT'), ('FSLR'), ('FTNT'), ('FTV'), ('GD'), ('GDDY'), ('GE'),
        ('GEHC'), ('GEN'), ('GEV'), ('GILD'), ('GIS'), ('GL'), ('GLW'), ('GM'), ('GNRC'), ('GOOGL'),
        ('GPC'), ('GPN'), ('GRMN'), ('GS'), ('GWW'), ('HAL'), ('HAS'), ('HBAN'), ('HCA'), ('HD'),
        ('HIG'), ('HII'), ('HLT'), ('HON'), ('HONA'), ('HOOD'), ('HPE'), ('HPQ'), ('HRL'), ('HSIC'),
        ('HST'), ('HSY'), ('HUBB'), ('HUM'), ('HWM'), ('IBKR'), ('IBM'), ('ICE'), ('IDXX'), ('IEX'),
        ('IFF'), ('INCY'), ('INTC'), ('INTU'), ('INVH'), ('IP'), ('IQV'), ('IR'), ('IRM'), ('ISRG'),
        ('IT'), ('ITW'), ('IVZ'), ('J'), ('JBHT'), ('JBL'), ('JCI'), ('JKHY'), ('JNJ'), ('JPM'),
        ('KDP'), ('KEY'), ('KEYS'), ('KHC'), ('KIM'), ('KKR'), ('KLAC'), ('KMB'), ('KMI'), ('KO'),
        ('KR'), ('KVUE'), ('L'), ('LDOS'), ('LEN'), ('LH'), ('LHX'), ('LII'), ('LIN'), ('LITE'),
        ('LLY'), ('LMT'), ('LNT'), ('LOW'), ('LRCX'), ('LULU'), ('LUV'), ('LVS'), ('LYB'), ('LYV'),
        ('MA'), ('MAA'), ('MAR'), ('MAS'), ('MCD'), ('MCHP'), ('MCK'), ('MCO'), ('MDLZ'), ('MDT'),
        ('MET'), ('META'), ('MGM'), ('MKC'), ('MLM'), ('MMM'), ('MNST'), ('MO'), ('MOS'), ('MPC'),
        ('MPWR'), ('MRK'), ('MRNA'), ('MRSH'), ('MRVL'), ('MS'), ('MSCI'), ('MSFT'), ('MSI'), ('MTB'),
        ('MTD'), ('MU'), ('NCLH'), ('NDAQ'), ('NDSN'), ('NEE'), ('NEM'), ('NFLX'), ('NI'), ('NKE'),
        ('NOC'), ('NOW'), ('NRG'), ('NSC'), ('NTAP'), ('NTRS'), ('NUE'), ('NVDA'), ('NVR'), ('NWSA'),
        ('NXPI'), ('O'), ('ODFL'), ('OKE'), ('OMC'), ('ON'), ('ORCL'), ('ORLY'), ('OTIS'), ('OXY'),
        ('PANW'), ('PAYX'), ('PCAR'), ('PCG'), ('PEG'), ('PEP'), ('PFE'), ('PFG'), ('PG'), ('PGR'),
        ('PH'), ('PHM'), ('PKG'), ('PLD'), ('PLTR'), ('PM'), ('PNC'), ('PNR'), ('PNW'), ('PODD'),
        ('PPG'), ('PPL'), ('PRU'), ('PSA'), ('PSKY'), ('PSX'), ('PTC'), ('PWR'), ('PYPL'), ('Q'),
        ('QCOM'), ('RCL'), ('RDDT'), ('REG'), ('REGN'), ('RF'), ('RJF'), ('RL'), ('RMD'), ('ROK'),
        ('ROL'), ('ROP'), ('ROST'), ('RSG'), ('RTX'), ('RVTY'), ('SBAC'), ('SBUX'), ('SCHW'), ('SHW'),
        ('SJM'), ('SLB'), ('SMCI'), ('SNA'), ('SNDK'), ('SNPS'), ('SO'), ('SOLV'), ('SPG'), ('SPGI'),
        ('SRE'), ('STE'), ('STLD'), ('STT'), ('STX'), ('STZ'), ('SW'), ('SWK'), ('SWKS'), ('SYF'),
        ('SYK'), ('SYY'), ('T'), ('TAP'), ('TDG'), ('TDY'), ('TECH'), ('TEL'), ('TER'), ('TFC'),
        ('TGT'), ('TJX'), ('TKO'), ('TMO'), ('TMUS'), ('TPL'), ('TPR'), ('TRGP'), ('TRMB'), ('TROW'),
        ('TRV'), ('TSCO'), ('TSLA'), ('TSN'), ('TT'), ('TTD'), ('TTWO'), ('TXN'), ('TXT'), ('TYL'),
        ('UAL'), ('UBER'), ('UDR'), ('UHS'), ('ULTA'), ('UNH'), ('UNP'), ('UPS'), ('URI'), ('USB'),
        ('V'), ('VEEV'), ('VICI'), ('VLO'), ('VLTO'), ('VMC'), ('VMRK'), ('VRSK'), ('VRSN'), ('VRT'),
        ('VRTX'), ('VST'), ('VTR'), ('VTRS'), ('VZ'), ('WAB'), ('WAT'), ('WBD'), ('WDAY'), ('WDC'),
        ('WEC'), ('WELL'), ('WFC'), ('WM'), ('WMB'), ('WMT'), ('WRB'), ('WSM'), ('WST'), ('WTW'),
        ('WY'), ('WYNN'), ('XEL'), ('XOM'), ('XYL'), ('XYZ'), ('YUM'), ('ZBH'), ('ZBRA'), ('ZTS')
)
SELECT u.ticker,
       CASE
           WHEN NOT EXISTS (
               SELECT 1 FROM company_listings cl
               WHERE upper(cl.ticker) = upper(u.ticker)
           ) THEN 'no company_listings row'
           ELSE 'no CIK identifier'
       END AS failure
FROM universe u
WHERE NOT EXISTS (
    SELECT 1
    FROM company_listings cl
    JOIN company_identifiers ci
      ON ci.company_id = cl.company_id
     AND ci.identifier_type = 'CIK'
    WHERE upper(cl.ticker) = upper(u.ticker)
)
ORDER BY u.ticker;
