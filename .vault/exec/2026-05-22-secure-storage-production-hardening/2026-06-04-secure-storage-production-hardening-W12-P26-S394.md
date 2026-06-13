---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S394'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s394-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S394`

Closed `AFR-292` for the locale developer CLI plaintext-exception slice.

## Description

- Audited `src/aeat/locales/cli.py` as a developer catalogue command surface over `LocaleManager`.
- Verified operator-facing Typer output uses `tr()` locale strings.
- Verified manager failures are converted into chained Typer parameter errors rather than being swallowed.
- Used vaultspec RAG semantic search to compare the CLI with adjacent locale manager and coverage tests.
- Updated the AFR register entry for `AFR-292` to `closed`.

## Outcome

`AFR-292` is closed as `plaintext-exception`. The locale CLI remains a narrow catalogue-maintenance boundary and does not introduce a storage backend, active-profile dependency, or plaintext persistence path outside the locale files managed by `LocaleManager`.

Validation passed:

- `uv run --no-sync ruff check src/aeat/locales/cli.py src/aeat/locales/test_cli.py src/aeat/locales/test_parity.py`
- `uv run --no-sync pytest -q src/aeat/locales/test_cli.py src/aeat/locales/test_parity.py::test_locale_set_cli_rejects_path_like_locale_without_writing`
- `PYTHONPATH=src uv run --no-sync -q python -m aeat.locales audit`
- `uvx vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Notes

No code change was required for this step; the work closes the register row with evidence and the existing focused tests.
