# Full SEC Universe Bulk Ingestion Runbook

## Overview
This runbook documents the procedure for running a full SEC EDGAR universe bulk ingestion using the optimized batch insert pipeline.

## Prerequisites
- PostgreSQL database with schema migrated
- SEC_USER_AGENT environment variable set
- Sufficient disk space (~200GB for full load)
- Network access to SEC API (data.sec.gov)

## Configuration

### Environment Variables
```bash
export SEC_USER_AGENT="your-app/1.0 contact@example.com"
export DATABASE_URL="postgresql://user:pass@host:5432/db"
export DATA_RAW_DIR="./data/raw"  # optional
```

### Key Configuration Constants (in bulk_ingest.py)
- `FACTS_PER_TRANSACTION = 500` - Facts per database transaction
- `CHECKPOINT_INTERVAL_SECONDS = 30.0` - Checkpoint frequency
- `NETWORK_RETRY_INTERVAL = 10.0` - Network retry interval (seconds)
- `GRACEFUL_SHUTDOWN_TIMEOUT = 15.0` - Shutdown timeout (seconds)

## Running the Full Load

### Dry Run (Validation)
```bash
financial-db sec bulk-ingest --dry-run
```

### Full Load (with confirmation)
```bash
financial-db sec bulk-ingest --confirm
```

### Limited Test Run
```bash
financial-db sec bulk-ingest --limit 100 --confirm
```

### Resume from Checkpoint
```bash
financial-db sec bulk-ingest --checkpoint-file ./data/checkpoints/sec_bulk/full_universe_checkpoint.json --confirm
```

## Monitoring Progress

### Checkpoint File
Location: `./data/checkpoints/sec_bulk/full_universe_checkpoint.json`

Format:
```json
{
  "dataset": "full_universe",
  "provider": "SEC EDGAR",
  "last_processed_cik": "0001652044",
  "companies_processed": 1234,
  "facts_processed": 567890,
  "filings_processed": 45678,
  "updated_at": "2024-01-15T10:30:00+00:00"
}
```

### Progress Monitoring
```bash
# Watch checkpoint file
watch -n 30 cat ./data/checkpoints/sec_bulk/full_universe_checkpoint.json

# Query database progress
psql -U financial -d financial_database -c "
SELECT ci.identifier_value, c.legal_name, COUNT(ff.id) as facts
FROM financial_facts ff
JOIN companies c ON ff.company_id = c.id
JOIN company_identifiers ci ON c.id = ci.company_id
WHERE ci.identifier_type = 'CIK'
GROUP BY ci.identifier_value, c.legal_name
ORDER BY ci.identifier_value
LIMIT 20;
"
```

## Interruption and Resume

### Graceful Shutdown
Press Ctrl+C to initiate graceful shutdown:
1. Stops initiating new requests
2. Completes current transaction
3. Saves checkpoint atomically
4. Closes connections cleanly

### Resume After Interruption
```bash
financial-db sec bulk-ingest --checkpoint-file ./data/checkpoints/sec_bulk/full_universe_checkpoint.json --confirm
```

### Forced Kill Recovery
If process is killed (SIGKILL/power loss):
1. Restart with same checkpoint file
2. System will skip already processed companies
3. Last uncommitted chunk (max 500 facts) will be re-ingested
4. Idempotency ensures no duplicates

## Performance Expectations (validated)

| Metric | Value (608 companies) | Extrapolated (10,388) |
|--------|-----------------------|----------------------|
| Time | ~51 min | ~14.5 hours |
| Facts | ~12.3M | ~213M |
| Filings | ~130K | ~2.2M |
| Database Size | ~10 GB | ~170–200 GB |
| Facts/Company | ~20,500 | ~20,500 |

A 608-company stress test was completed and validated (see
`docs/validation_report.md`): zero duplicates/orphans, historical coverage back
to 2009, and 10 expected 404s (non-XBRL filers).

## PostgreSQL Tuning

Apply the recommended settings before the full load (see
`scripts/tune_postgres.sql`):

```bash
psql "postgresql://financial@localhost:5432/financial_database" -f scripts/tune_postgres.sql
```

Settings applied: `maintenance_work_mem=512MB`, `work_mem=64MB`,
`synchronous_commit=off`, `max_wal_size=4GB`, `checkpoint_timeout=15min`.

## Pre-Flight Validation

Before launching the full load, run the integrity audit and historical coverage
queries:

```bash
psql "postgresql://financial@localhost:5432/financial_database" -f scripts/integrity_audit.sql
psql "postgresql://financial@localhost:5432/financial_database" -f scripts/verify_history.sql
```

## Running the Full Load

```bash
SEC_USER_AGENT="YourApp/1.0 you@example.com" \
.venv/bin/python -m financial_database.cli sec bulk-ingest --confirm
```

The checkpoint is source-aware; re-running the same command resumes from the
last processed CIK. Use `--force` to ignore prior progress and start over.

## Data Integrity Verification

### Post-Load Checks
```bash
# Check for duplicates
psql -U financial -d financial_database -c "
SELECT ci.identifier_value, COUNT(*) as cnt
FROM company_identifiers ci
JOIN companies c ON ci.company_id = c.id
WHERE ci.identifier_type = 'CIK'
GROUP BY ci.identifier_value
HAVING COUNT(*) > 1;
"

psql -U financial -d financial_database -c "
SELECT ff.company_id, ff.concept, ff.period_start, ff.period_end, COUNT(*) as cnt
FROM financial_facts ff
GROUP BY ff.company_id, ff.concept, ff.period_start, ff.period_end
HAVING COUNT(*) > 1;
"
```

### Expected Results
- Zero duplicate companies (by CIK)
- Zero duplicate filings (by accession_number)
- Zero duplicate facts (by unique constraint)
- Zero orphaned records

## Troubleshooting

### Common Issues

| Issue | Resolution |
|-------|------------|
| 404 on companyfacts | Company may not have XBRL data; logged and skipped |
| 429 Rate Limit | Client retries with Retry-After header |
| Network timeout | Retries every 10 seconds indefinitely |
| Database connection lost | Checkpoint saved; resume after reconnect |
| Out of memory | Reduce FACTS_PER_TRANSACTION |

### Performance Tuning
- Increase `FACTS_PER_TRANSACTION` for faster inserts (more memory)
- Decrease `CHECKPOINT_INTERVAL_SECONDS` for more frequent checkpoints
- Adjust `NETWORK_RETRY_INTERVAL` based on network stability

## Backup Strategy

### Pre-Load
```bash
pg_dump -U financial -d financial_database > pre_load_backup.sql
```

### Post-Load
```bash
pg_dump -U financial -d financial_database > post_load_backup.sql
```

## Contact
For issues during full load, check:
1. Checkpoint file for last processed CIK
2. Error logs in application output
2. Database integrity checks
3. SEC API status at https://www.sec.gov/developer

## Version History
- v1.0: Initial batch insert optimization
- v1.1: Added graceful shutdown and checkpointing
- v1.2: Network resilience with infinite retries
