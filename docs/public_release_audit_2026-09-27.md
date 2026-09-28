# Public release readiness audit — 2026-09-27

## Maintainer update — 2026-09-28

This is a dated snapshot, not the current release checklist. The maintainer
confirmed that the account-associated author email in existing Git history is
acceptable; **the history will not be rewritten**. The repository now has an
MIT license, contribution/security/community policies, CI, issue and
pull-request templates, and a bilingual README. The README documents the SEC
reference snapshot and the current Yahoo Finance price-ingestion path. Review
the current README and GitHub settings before publishing; other commit-author
metadata has not been rewritten.

Audit of **Financial-DataBase** before making the repository public.
Read-only: nothing was modified while producing it. `gitleaks` and
`trufflehog` are not installed on this machine, so the scan is pattern-based
(§1 lists the patterns).

Note on volume: the repository tracks a large SEC reference snapshot
(`company_tickers*.json`), so raw `git log -p` output is enormous. The counts
below come from counted greps over the full patch history, not from reading
it.

## 1. Secrets

### 1.1 History (`git log -p --all`)

| Pattern | Hits | Verdict |
| --- | ---: | --- |
| `<SEC_CONTACT_EMAIL>` (the personal address) | 4 | **Real exposure** (2 lines in one commit) |
| `@gmail\.com` | 4 | same |
| private-key headers (RSA / OpenSSH / PGP) | 0 | clean |
| `api[_-]?key` | 0 | clean |
| `password` | 3 | false positives: `TEST_DB_PASSWORD` env default `"test"` and `plain_password`-style identifiers in test code |
| `postgres://user:pass@` | 0 | no credential in a connection string |

All four e-mail occurrences are in `3537f0b` (the live SEC refresh report)
and were removed from HEAD by `1662dbe`.

### 1.2 HEAD

| Finding | Verdict |
| --- | --- |
| `tests/conftest.py:14 TEST_DB_PASSWORD = os.environ.get("TEST_DB_PASSWORD", "test")` | placeholder, overridable, safe |
| `docs/architecture*.md` "Registro estructurado sin secretos" | prose, safe |

**No live secret in HEAD.** `.env` was never tracked (`.gitignore:25
**.env*`); only `.env.example` is.

## 2. Personal information

**HEAD — 3 files contain `~`:**

| File | Lines |
| --- | --- |
| `docs/cboe_reax_fix_report.md` | 50, 56 |
| `docs/runbook_daily_update.md` | 79, 82, 85 (cron examples) |
| `docs/stale_sweep_2026-09-27.md` | 14 |

**Personal e-mail addresses in HEAD: 0** (this document refers to the address
only as `<SEC_CONTACT_EMAIL>`). No macOS or Windows user paths, no
internal hostnames or IPs. README has **no absolute paths**.

**History:** the four e-mail lines plus `name="Jaime"` nowhere (FDB never had
a SEC_NAME default).

## 3. Commit authors

```
jdejusto@users.noreply.github.com   <- preferred (recent commits)
<SEC_CONTACT_EMAIL>                <- personal
jdejusto@example.com                <- placeholder
noreply@anthropic.com               <- third-party agent identity
```

**`noreply@anthropic.com` deserves a decision before publishing.** It is a
non-GitHub, non-personal-looking but third-party-controlled address; it is
the address an AI assistant commits under, and it is unusual in a public
repository. It is not a secret, and it cannot be removed without rewriting
history, so the honest options are: accept it (it reads as a bot account) or
rewrite. See `docs/history_rewrite_recommendation.md`.

**Recommendation:** set `jdejusto@users.noreply.github.com` as the
account-wide default so future commits do not add more identities.

## 4. .gitignore

**Tracked files matching the sensitive patterns: none.** Verified: no `.env`,
no `data/raw/`, no `data/cache/`, no `data/reports/`, no logs, no
checkpoints, no `__pycache__`, no `.pyc`, no `.venv`, no `.DS_Store`.

`db/migrations/*.sql` **is** tracked, which is correct: migrations are source,
not runtime output.

No gaps.

## 5. Dependencies

- `pyproject.toml`: `requires-python = ">=3.13"`, no `git+`, no `file://`, no
  personal package index.
- No hardcoded connection string with a real password. The CLI default is
  `postgresql://financial:test@localhost:5432/financial_database`, overridable
  by `DATABASE_URL`.
- Tests: `tests/conftest.py` reads `TEST_DB_NAME`, `TEST_DB_USER`,
  `TEST_DB_PASSWORD`, `TEST_DB_HOST`, `TEST_DB_PORT` from the environment with
  development defaults, and the unit suite (158 tests) does not need a live
  database. The integration tests do, and they target
  `financial_database_test`.
- No personal database name is required; `financial` is the local role, and
  everything is parameterised.

## 6. Documentation

| Item | Status |
| --- | --- |
| `README.md` | present, no absolute paths |
| `.env.example` | present (`SEC_USER_AGENT`, `DATABASE_URL` with placeholders) |
| `LICENSE` | **MISSING** |
| `CONTRIBUTING.md` | **MISSING** |
| `CODE_OF_CONDUCT.md` | **MISSING** |
| `SECURITY.md` | **MISSING** |
| `CHANGELOG.md` | missing (optional) |
| `docs/` | strong: SEC 403 investigation, sweep reports, pg_stat_statements diagnosis, audit documents |

## 7. GitHub configuration

| Item | Status |
| --- | --- |
| `.github/dependabot.yml` | present |
| `.github/pull_request_template.md` | present |
| `.github/workflows/` | **MISSING** — no CI |
| `.github/ISSUE_TEMPLATE/` | **MISSING** |

## 8. Recommendations, by priority

**Must do before publishing**

1. **Decide the history question** — 4 lines of personal e-mail in
   `3537f0b`, plus the `noreply@anthropic.com` author identity. This
   repository is much smaller than Value Investing (3 commits vs ~120), so a
   rewrite here is far cheaper if the user wants it. See
   `docs/history_rewrite_recommendation.md`.
2. **Add a LICENSE** (MIT).
3. **Add `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`.**
4. **Add a minimal CI workflow** (the unit suite needs no database, so this
   is straightforward here).

**Should do**

5. **Reduce the absolute paths** in `docs/cboe_reax_fix_report.md`,
   `docs/runbook_daily_update.md` and `docs/stale_sweep_2026-09-27.md` to
   relative forms.
6. **Add issue templates.**
7. Consider whether the committed SEC `company_tickers*.json` snapshots are
   wanted in a public repository: they are large (tens of thousands of
   lines), third-party data, and add noise to the diff. Keeping them is
   defensible (reproducibility), but a short note in the README explaining
   their provenance and licence status would help.

**Optional**

8. Repository topics and description.
9. `CHANGELOG.md` when releases start being tagged.
