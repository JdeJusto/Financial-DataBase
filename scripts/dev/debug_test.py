import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

REPO_ROOT = Path(__file__).resolve().parents[2]
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    sys.exit(
        "Set DATABASE_URL to a development/test database before running this helper."
    )

conn = psycopg.connect(database_url, row_factory=dict_row)

print("Connected to database")


# Add execute_script method
def execute_script(script_path, params=None):
    with open(script_path, "r") as f:
        script_content = f.read()

    # Replace parameters in the script
    if params:
        for key, value in params.items():
            if isinstance(value, str):
                # For string values, we need to quote them and escape single quotes
                escaped_value = value.replace("'", "''")
                script_content = script_content.replace(f":{key}", f"'{escaped_value}'")
            elif isinstance(value, list):
                # Handle array parameters (for IN clauses etc.)
                if all(isinstance(item, str) for item in value):
                    quoted_items = [
                        "'" + item.replace("'", "''") + "'" for item in value
                    ]
                    array_str = f"ARRAY[{','.join(quoted_items)}]"
                    script_content = script_content.replace(f":{key}", array_str)
                else:
                    array_str = f"ARRAY[{','.join(str(item) for item in value)}]"
                    script_content = script_content.replace(f":{key}", array_str)
            else:
                # For numeric values
                script_content = script_content.replace(f":{key}", str(value))

    print("DEBUG: About to execute script (first 150 chars):")
    print(repr(script_content[:150]))

    try:
        with conn.cursor() as cur:
            cur.execute(script_content)
            if cur.description:  # If it's a SELECT query
                columns = [desc[0] for desc in cur.description]
                results = []
                for row in cur.fetchall():
                    results.append(dict(zip(columns, row)))
                return results
            else:
                # For non-SELECT queries, return empty list
                return []
    except Exception as e:
        print(f"ERROR: {e}")
        print("Script content:")
        print(script_content)
        raise


# Attach the method to the connection object
conn.execute_script = execute_script

# Test the connection
print("Testing company overview script...")
try:
    result = conn.execute_script(
        str(REPO_ROOT / "scripts/analysis/company_overview.sql"),
        {"cik": "0000320193"},
    )
    print("SUCCESS: Result:", result)
except psycopg.Error as e:
    print("FAILED:", e)

conn.close()
