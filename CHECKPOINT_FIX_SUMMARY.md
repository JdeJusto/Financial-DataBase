# Fix for SEC Bulk Ingestion Resume Logic

## Problem
The SEC bulk ingestion resume logic had a bug where if a checkpoint's `last_processed_cik` was higher than any CIK in the current company universe, all companies would be skipped during resume, resulting in zero companies being processed.

This occurred in three methods:
1. `ingest_full_universe` (API-based approach)
2. `ingest_companyfacts` (bulk ZIP file approach)  
3. `ingest_submissions` (bulk ZIP file approach)

The root cause was the simple comparison: `if checkpoint.last_processed_cik and cik <= checkpoint.last_processed_cik: continue`

When `last_processed_cik` was from a previous run with a different/universe (e.g., processing all SEC companies) and the current run had a subset (e.g., only S&P 500 companies), the checkpoint CIK would be higher than all current CIKs, causing all to be skipped.

## Solution
Added intelligent checkpoint resume logic that:

1. **Checks if checkpoint CIK exists in current list**: If found, start from the next company
2. **Handles missing checkpoint CIK**: If not found, scans for first company with CIK > checkpoint.last_processed_cik
3. **Fixes the bug case**: When all current CIKs <= checkpoint.last_processed_cik, start from beginning (index 0)
4. **Includes detailed logging**: Warns when the stale checkpoint situation is detected and handled

## Files Modified
- `src/financial_database/providers/sec/bulk_ingest.py`

## Specific Changes
### 1. ingest_full_universe method (~lines 1632-1668)
Added checkpoint resume logic before the main processing loop that:
- Sorts companies by CIK for proper ordering
- Handles the three cases for checkpoint positioning
- Processes companies starting from the calculated `start_index`

### 2. ingest_companyfacts method (~lines 556-594)  
Added similar logic for the companyfacts bulk import:
- Sorts the companies_to_process list by CIK
- Implements the same three-case checkpoint handling
- Processes from calculated start_index

### 3. ingest_submissions method (~lines 908-953)
Added equivalent logic for submissions bulk import:
- Extracts CIKs from submission filenames
- Applies the same three-case checkpoint handling
- Processes files from calculated start_index

## Test Added
Added test case `test_checkpoint_handles_stale_checkpoint_higher_than_all_ciks` to `tests/integration/test_bulk_ingest_resume.py` that verifies:
- When checkpoint CIK is higher than all current CIKs, processing starts from beginning
- All companies in current universe are processed
- Checkpoint is properly updated during processing

## Verification
- All existing tests pass (20/20 in test_bulk_ingest_resume.py, 12/12 in test_bulk_ingest_full_universe.py)
- Manual test confirms the fix works for the reported bug scenario
- No syntax errors introduced
- Logic handles edge cases (empty lists, normal resume, etc.)

## Impact
Fixes the issue where resuming SEC bulk ingestion would process zero companies when:
- Checkpoint was from a previous run with different company universe
- Current run has subset of companies (different filtering, limits, etc.)
- Checkpoint's last_processed_cik is higher than any CIK in current universe

Now correctly handles this case by processing all companies in the current universe, ensuring data completeness.