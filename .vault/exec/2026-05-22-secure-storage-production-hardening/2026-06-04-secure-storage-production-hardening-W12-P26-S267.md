---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S267'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s267-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S267`

Closed `AFR-165` for user-profile lifecycle manifest-discovery storage.

## Description

- Hardened `src/aeat/application/user_profile/_lifecycle.py` so duplicate-profile, tombstoned-profile, and schema-validation refusals use stable translated messages with raw identifiers kept in structured context.
- Verified lifecycle event history persists through the registered `aeat.domain.buckets.event_history` secure-object namespace at `FINANCIAL` sensitivity.
- Added real-runtime tests covering translated exception keys, profile-id redaction from rendered error strings, and SQLite-at-rest encryption for lifecycle event payload values.
- Closed `S267` through `vaultspec-core vault plan step check` and manually aligned `AFR-165`.

## Outcome

`AFR-165` is closed. Lifecycle is now enrolled as a manifest-discovery surface with localized, sanitized refusal errors and secure bucket-event history persistence: operator labels and source profile ids are available after authorized decrypt, while the backing SQLite file stores them through the encrypted secure-object column.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/user_profile/_lifecycle.py src/aeat/application/user_profile/test_lifecycle.py`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/test_lifecycle.py`
- `PYTHONPATH=src uv run --no-sync -q python -m aeat.locales audit`

## Notes

The plan check still reports the existing `PLAN022` monotonic-order warning only.
