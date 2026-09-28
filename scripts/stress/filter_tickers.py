#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

# Read the stress test CIKs
REPO_ROOT = Path(__file__).resolve().parents[2]
stress_ciks_file = REPO_ROOT / "data" / "stress_test_ciks.txt"
if not stress_ciks_file.exists():
    print(f"Error: {stress_ciks_file} not found")
    sys.exit(1)

with open(stress_ciks_file) as f:
    stress_ciks = {line.strip() for line in f if line.strip()}
print(f"Loaded {len(stress_ciks)} CIKs from stress test list")

# Determine the path to the raw company_tickers_exchange.json
# The client stores raw data in DATA_RAW_DIR/reference/company_tickers_exchange.json
raw_dir = Path(os.environ.get("DATA_RAW_DIR", str(REPO_ROOT / "data" / "raw")))
if not raw_dir.is_absolute():
    raw_dir = REPO_ROOT / raw_dir
raw_dir = raw_dir / "sec" / "reference"
tickers_file = raw_dir / "company_tickers_exchange.json"

if not tickers_file.exists():
    print(
        f"Error: {tickers_file} not found. Please run a dry-run first to download the raw data."
    )
    sys.exit(1)

print(f"Reading {tickers_file}")
with open(tickers_file) as f:
    data = json.load(f)

# The data is expected to be a list under the key "data" (from the client's get_company_tickers)
# But the raw file from SEC is just an array? Let's check the structure.
# Actually, the client's get_company_tickers expects the SEC format:
#   SEC_COMPANY_TICKERS_URL returns a JSON with a "data" key that is an array.
# However, the raw file saved by the client is the raw JSON from the SEC, which has the "data" key.
# Let's look at the client's _save_raw_response: it saves the raw bytes.
# So the file we have is the full JSON from the SEC.

# If the file has a "data" key, use that, otherwise assume the root is the array.
if isinstance(data, dict) and "data" in data:
    array_data = data["data"]
else:
    array_data = data

print(f"Total entries in raw file: {len(array_data)}")

# Filter: each element is an array: [cik, name, ticker, exchange, sic, sic_description, owner_org]
filtered = []
for item in array_data:
    if len(item) >= 1:
        cik = str(item[0]).zfill(10)
        if cik in stress_ciks:
            filtered.append(item)

print(f"Filtered to {len(filtered)} entries")

# Wrap in the expected format if the original had a "data" key
if isinstance(data, dict) and "data" in data:
    output_data = {"data": filtered}
else:
    output_data = filtered

# Write to a temporary file
output_file = Path("/tmp/filtered_company_tickers_exchange.json")
with open(output_file, "w") as f:
    json.dump(output_data, f, indent=2)

print(f"Written filtered data to {output_file}")
print(f"Set environment variable: export SEC_CUSTOM_TICKERS_URL='{output_file}'")
