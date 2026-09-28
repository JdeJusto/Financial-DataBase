# Security Policy

## Reporting a vulnerability

**Do not open a public issue for a security problem.**

Report it privately through GitHub's private reporting for this repository
(**Security → Report a vulnerability**). If private reporting is unavailable,
email the maintainer at <mailto:jaimedejusto@gmail.com> and ask for a secure
channel before sending sensitive details. Do not open a public issue with
reproduction steps or vulnerability details.

Include: affected version or commit, reproduction steps, impact, and any
suggested mitigation. Expect an acknowledgement within a week.

## What counts as a vulnerability here

- Anything that leaks credentials, connection strings, API keys or personal
  data that is committed to the repository.
- SQL injection or unsafe dynamic query construction in the ingestion or the
  analysis scripts. Parameterised queries are the rule; string interpolation
  of user input is not.
- Unsafe deserialization reachable from a normal run (for example `pickle` on
  untrusted input).
- Path traversal in the raw-document or report paths (a company or filing name
  escaping its directory).
- Anything that causes the SEC ingestion to violate its fair-access rules
  (missing or non-compliant `User-Agent`, unbounded request bursts).

## Non-vulnerabilities

- The SEC answering HTTP 403/429. That is upstream rate limiting or a
  non-compliant contact, documented in `docs/sec_403_investigation.md`.
- A report that only needs a configuration change you have not made yet (no
  `DATABASE_URL`, no `SEC_USER_AGENT` in your `.env`).

## Supported versions

| Version | Supported |
| --- | --- |
| `main` | yes |
| older commits / tags | no — pin to `main` and re-run the migrations |

This project has no release tags yet; `main` is the supported line, and the
schema is defined by the numbered migrations in `db/migrations/`.

## Disclosure policy

1. Report privately.
2. Confirm receipt, then confirm the fix and its release.
3. Publish the advisory after the fix is available, unless disclosure would
   put users at risk.
4. Credit the reporter unless anonymity is preferred.

We will not pursue legal action over good-faith research that follows this
policy, respects other users' data, and does not degrade the service.
