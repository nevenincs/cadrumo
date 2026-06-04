---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
step_id: 'S270'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s270-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S270`

Closed `AFR-168` for user-profile secure repository runtime-default custody.

## Description

- Audited the user-profile value and snapshot repository as the runtime-bound secure-object persistence layer.
- Replaced raw missing profile and missing snapshot messages with translated AEAT error keys and structured context.
- Added debug diagnostics to the intentionally nonblocking output-language cache invalidation path.
- Updated real secure-object repository tests to assert the translated error keys and context.
- Used a narrow vaultspec RAG semantic search to compare the repository with adjacent runtime and lifecycle wiring.

## Outcome

`AFR-168` is closed as `runtime-default`. The repository remains bucket-runtime bound,
uses registered namespace constants and strict envelope records, and no longer has raw
not-found messages or silent cache-invalidation swallowing.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/user_profile/_repository.py src/aeat/application/user_profile/test_repository.py src/aeat/locales`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/test_repository.py`
- `PYTHONPATH=src uv run --no-sync -q python -m aeat.locales audit`

## Notes

The broader plan check still reports only the existing `PLAN022` monotonic-order warning.
