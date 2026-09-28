---
name: Bug report
about: Something behaves differently from what the documentation says
title: "[bug] "
labels: bug
assignees: ''
---

**What happened**

<!-- What you observed, including the exact wording of any warning or error. -->

**What you expected**

**Reproduction**

```bash
# the exact command, with arguments
```

**Environment**

- Financial-DataBase commit: `git rev-parse --short HEAD`
- Python: `python --version`
- Database: PostgreSQL `SELECT version();`
- Command and flags used (e.g. `sec sync <CIK>`, `prices update --limit 10`)

**Relevant log output**

<!--
The importer's own output (`python -m financial_database.cli sec sync <CIK>`)
and, for ingestion problems, the row counts it reports
(records_inserted / records_skipped) plus the import_runs row for that
company (`SELECT pipeline, status, company_id, duration_seconds FROM
import_runs ORDER BY started_at DESC LIMIT 5;`).
DO NOT paste a .env, a connection string with a password, or any
personal e-mail.
-->

**Anything else**

<!-- Screenshots of the terminal output if they help. -->
