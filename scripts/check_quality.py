#!/usr/bin/env python3
"""Populate ``data_quality_issues`` from the normalized core financials.

Run after the normalization migration (0022) and after refreshing
``core_financials``. It only reads ``core_financials`` / ``balance_effective``
and writes the quality table; ``financial_facts`` is untouched.

Usage:
    python scripts/check_quality.py --full
"""

from __future__ import annotations

import argparse
import os

import psycopg

DEFAULT_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://financial:test@localhost:5432/financial_database",
)

LATEST_CORE = """
    CREATE TEMP VIEW latest_core AS
    SELECT cf.*
    FROM core_financials cf
    JOIN (
      SELECT company_id, fiscal_year, max(period_end) AS period_end
      FROM core_financials
      WHERE fiscal_year >= 2023
      GROUP BY company_id, fiscal_year
    ) l
      ON l.company_id = cf.company_id
     AND l.fiscal_year = cf.fiscal_year
     AND l.period_end = cf.period_end
"""

ISSUE_QUERIES = {
    "negative_revenue": """
        INSERT INTO data_quality_issues
          (company_id, fiscal_year, field, issue_type, severity, value)
        SELECT company_id, fiscal_year, 'revenue', 'negative_revenue', 'error',
               min(revenue)
        FROM latest_core
        WHERE revenue < 0
        GROUP BY company_id, fiscal_year
        ON CONFLICT DO NOTHING
    """,
    "unbalanced": """
        INSERT INTO data_quality_issues
          (company_id, fiscal_year, field, issue_type, severity, value)
        SELECT company_id, fiscal_year, 'balance', 'unbalanced', 'error',
               min(diff)
        FROM (
          SELECT be.company_id, be.fiscal_year,
                 abs(be.total_assets - (be.liabilities_effective + be.stockholders_equity))
                   / nullif(be.total_assets, 0) AS diff
          FROM balance_effective be
          JOIN latest_core lc
            ON lc.company_id = be.company_id
           AND lc.fiscal_year = be.fiscal_year
           AND lc.period_end = be.period_end
          WHERE be.total_assets IS NOT NULL
            AND be.liabilities_effective IS NOT NULL
            AND be.stockholders_equity IS NOT NULL
        ) t
        WHERE diff > 0.01
        GROUP BY company_id, fiscal_year
        ON CONFLICT DO NOTHING
    """,
    "absurd_margin": """
        INSERT INTO data_quality_issues
          (company_id, fiscal_year, field, issue_type, severity, value)
        SELECT company_id, fiscal_year, 'gross_margin', 'absurd_margin', 'error',
               min(gross_profit)
        FROM latest_core
        WHERE revenue > 0 AND gross_profit > revenue * 1.01
        GROUP BY company_id, fiscal_year
        ON CONFLICT DO NOTHING
    """,
    "future_date": """
        INSERT INTO data_quality_issues
          (company_id, fiscal_year, field, issue_type, severity, value)
        SELECT company_id, fiscal_year, 'period_end', 'future_date', 'warning',
               min(extract(year FROM period_end))
        FROM latest_core
        WHERE period_end > CURRENT_DATE + INTERVAL '2 years'
        GROUP BY company_id, fiscal_year
        ON CONFLICT DO NOTHING
    """,
    "zero_revenue": """
        INSERT INTO data_quality_issues
          (company_id, fiscal_year, field, issue_type, severity, value)
        SELECT company_id, fiscal_year, 'revenue', 'zero_revenue', 'warning', 0
        FROM latest_core
        WHERE revenue = 0
        GROUP BY company_id, fiscal_year
        ON CONFLICT DO NOTHING
    """,
}


def run(database_url: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(LATEST_CORE)
            cur.execute("TRUNCATE data_quality_issues")
            for name, sql in ISSUE_QUERIES.items():
                cur.execute(sql)
                counts[name] = cur.rowcount
            cur.execute("SELECT count(*) FROM data_quality_issues")
            counts["total"] = cur.fetchone()[0]
        conn.commit()
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=DEFAULT_URL)
    parser.add_argument("--full", action="store_true", help="Scan every company")
    args = parser.parse_args()
    counts = run(args.database_url)
    for name, count in counts.items():
        print(f"{name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
