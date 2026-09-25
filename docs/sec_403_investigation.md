# SEC HTTP 403 investigation (2026-09-24 / 2026-09-25)

## Summary

SEC EDGAR returned HTTP 403 on 2026-09-24 (targeted `sec sync` failed with
`SECClientError: HTTP 403`, 0 records) and intermittently during this
investigation. Spaced, same-endpoint probes isolate **two deterministic
causes and one environment non-cause**:

1. **User-Agent policy.** SEC blocks generic client UAs (`curl/*`,
   `python-requests/*`) and UAs whose contact address uses a **github.com
   domain** — including `users.noreply.github.com`, GitHub's default
   "noreply" address. A descriptive agent with a normal email domain works.
2. **Rate limit.** SEC's fair-access guidance is ≤10 requests/second per
   IP; bursts return 403 (not 429). Reproduced: a ~10-probe burst turned
   working UAs into 403s until a cooldown restored 200s.
3. **Not an environment block, not a SEC outage.** Other hosts work and
   SEC itself answers 200 as soon as the UA/rate rules are satisfied.

The 2026-09-24 `sec_sync` failure is most consistent with (1): the
automation was using a `@users.noreply.github.com` contact (this
repository's commit identity), which SEC deterministically blocks.

## Evidence

### User-Agent matrix (spaced ≥15 s probes, same endpoint and minute)

```
200  ValueInvesting audit contact@example.com
200  ValueInvesting-Audit/1.0 contact@example.com
200  ValueInvesting-Audit/1.0 contact@example.org
200  ValueInvesting-Audit/1.0 contact@noreply.dev
403  ValueInvesting-Audit/1.0 jdejusto@users.noreply.github.com
403  ValueInvesting audit jdejusto@users.noreply.github.com
403  Foo/1.0 contact@users.noreply.github.com
403  ValueInvesting-Audit/1.0 contact@github.com
403  curl/8.5.0
403  python-requests/2.31.0
```

→ The **github.com address family** and generic library UAs are blocked;
"noreply" in a normal domain is fine.

### Rate limit

A burst of ~10 probes in about one second produced 403s for UAs that answer
200 when spaced (and 200 again after a cooldown). SEC returns 403 — not 429
— when the ≤10 req/s guidance is exceeded.

### Endpoints and environment

| Request | Result |
|---|---|
| `data.sec.gov/api/xbrl/companyfacts/…json`, compliant UA | 200 |
| `www.sec.gov/files/company_tickers.json`, compliant UA | 200 |
| `data.sec.gov/` (root path, no resource) | 403 by design |
| `www.sec.gov/` with generic UA | 403 (UA policy) |
| `www.google.com/` | 200 (general egress fine) |
| proxy environment variables | none configured |

No `.env` file and no `SEC_USER_AGENT` in the shell: `sec *` commands
refuse to run until one is configured (that is a configuration error, not a
403).

### Real client

- `SECClient.get_company_tickers()` with `contact@example.com` → 10,413
  companies in 0.7 s; second call 0.000 s (memoization).
- Same call with a `@users.noreply.github.com` contact →
  `SECClientError: HTTP 403`.

## Root cause

1. **UA policy (deterministic).** Do not use a github.com contact address
   (nor "github" branding) in `SEC_USER_AGENT`, and never a bare library
   UA. Use `AppName/Version your_real_email@your_domain`.
2. **Bursts (>10 req/s) return 403.** Keep targeted syncs ≤2 concurrent
   (`config/refresh.yaml → refresh_workers: 2`) and avoid hammering.

## Workarounds tested

| Workaround | Result |
|---|---|
| Descriptive UA, normal email domain | 200 |
| UA with github.com contact | 403 (blocked) |
| Spacing requests ≥15 s | 200 (rate limit respected) |
| Retry after cooldown | 200 |
| Preflight probe (HEAD, before refresh) | works as an availability gate |

## Recommended action

1. Configure a compliant UA — **not** a github.com address:
   `SEC_USER_AGENT="FinancialDataBase/1.0 you@your-domain.com"`.
2. Keep the preflight (implemented in Value Investing:
   `backend/services/sec_health.py`, wired into
   `backend/services/refresh_service.py`): on probe failure the SEC refresh
   is skipped with one clear note and analysis continues with the stored
   fundamentals.
3. ≤2 concurrent `sec sync`; let the client rate limiter do its job.
4. On 403: check the UA first; if compliant, back off for hours and retry
   without hammering.

## How to detect when SEC access is restored

```
curl -sI -o /dev/null -w "%{http_code}\n" \
  -H "User-Agent: $SEC_USER_AGENT" \
  https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json
# 200 -> OK; 403 -> UA policy (check the domain) or rate limit (wait)
```

In Value Investing, `backend.services.sec_health.check_sec_availability()`
performs exactly this probe (HEAD, cached 120 s, one retry) before any
targeted refresh. A single-company smoke test is also enough:

```
.venv/bin/python -m financial_database.cli sec sync 0000320193
```
