# Financial Database

## Mission

Build a reliable financial market data platform.

## Architecture

Provider
→ Raw data
→ Parser
→ Validator
→ Repository
→ PostgreSQL

## Rules

1. Never commit secrets.
2. Never use SQLite.
3. Never bypass migrations.
4. All imports must be idempotent.
5. All external API clients must implement retries.
6. All external requests must respect provider rate limits.
7. Raw data must be preserved when legally and technically possible.
8. Every financial fact must retain source provenance.
9. Database changes require a migration.
10. New providers require tests.
11. Never silently discard malformed financial data.
12. Never overwrite historical financial facts without provenance.
13. Do not introduce dependencies without justification.
14. Do not modify CI security settings without explicit approval.

## Testing

Every feature must include tests.

Database changes require integration tests.

## Git

Do not commit directly to main.

Use feature branches and pull requests.