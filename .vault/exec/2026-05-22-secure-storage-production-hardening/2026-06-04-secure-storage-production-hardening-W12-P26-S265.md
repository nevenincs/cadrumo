---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S265'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s265-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S265`

Closed `AFR-163` for profile cross-store integrity validation.

## Description

- Audited `src/aeat/application/user_profile/_integrity.py` as the read-time manifest/secure-record consistency gate.
- Found cross-store drift errors embedded raw profile IDs, directory names, manifest IDs, record IDs, and lifecycle status values in exception text.
- Replaced raw integrity messages with stable sanitized `ProfileIntegrityError` messages.
- Added translation keys for identity and lifecycle integrity mismatches through `python -m aeat.locales`.
- Preserved repair usefulness through structured context containing only store-name mismatch categories.
- Updated tests to assert translated keys, sanitized context, and absence of raw identifiers or status values in rendered errors.
- Closed `S265` through `vaultspec-core vault plan step check` and manually aligned `AFR-163`.

## Outcome

`AFR-163` is closed. Profile integrity validation still fails closed on cross-store drift, but rendered errors no longer disclose raw profile identifiers or physical-store values.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/user_profile/_integrity.py src/aeat/application/user_profile/test_aggregate.py`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/test_aggregate.py`
- `PYTHONPATH=src uv run --no-sync -q python -m aeat.locales audit`

## Notes

The plan check still reports the existing `PLAN022` monotonic-order warning only.
