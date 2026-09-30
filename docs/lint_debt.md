# Lint debt

## Status

No remaining lint debt as of 2026-09-30. `ruff check .` and
`ruff format --check .` are clean on the whole repo, and
`config/lint_baseline` (`0`/`0`) keeps the release gate strict.

## What the cleanup covered (84 errors → 0)

- **UP045 / UP006 / UP035**: modern annotations (`X | None`, builtin
  generics) and imports moved to `collections.abc`.
- **F401 / I001**: unused imports removed and import order fixed.
- **F841**: unused locals dropped (price importers, integration test).
- **BLE001**: the remaining blind `except Exception` sites are boundary
  catches (network/provider, per-record skip, duplicate-key detection) and
  now carry a documented `# noqa: BLE001`.
- **DTZ007**: Stooq dates parse with `date.fromisoformat` (no naive
  `datetime.strptime`).
- **RUF012**: mutable class attribute annotated `ClassVar`.
- **Formatting**: 15 files reformatted by `ruff format`.
