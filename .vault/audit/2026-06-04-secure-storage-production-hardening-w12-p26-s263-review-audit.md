---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S263]]'
---

# `secure-storage-production-hardening` `W12.P26.S263` Review

## S263-001 | HIGH | Aggregate mismatch errors leaked profile identifiers and labels

`src/aeat/application/user_profile/_aggregate.py` rejected cross-store mismatch states with messages containing raw profile UUIDs and operator labels. Those mismatches are precisely the failure mode most likely to be logged or surfaced during storage repair, so the error text was too detailed for a secure-storage boundary.

Disposition: fixed. The aggregate now raises a sanitized `UserProfileValidationError` with a stable fallback message, a locale key, and context limited to the mismatch category.

## S263-002 | HIGH | Pydantic error rendering could echo the entire input aggregate

The aggregate model used the shared strict frozen config directly. Pydantic validation errors may render input values unless `hide_input_in_errors` is enabled, which can expose the profile label and secure record representation even after the raised exception text is sanitized.

Disposition: fixed for this aggregate model through a local config that extends the shared strict frozen config with hidden input values.

## S263-003 | MEDIUM | Locale tooling requires literal translation-key call sites

The first pass used module constants for the new translation keys, but `aeat.locales audit` treated those keys as orphaned because the scanner discovers literal `translated_message=` values. The codebase convention is therefore literal key call sites for user-facing errors.

Disposition: fixed. The helper remains centralized for sanitized error construction, while the call sites use literal translation keys.

## S263-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/user_profile/_aggregate.py src/aeat/application/user_profile/test_aggregate.py`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/test_aggregate.py`
- `PYTHONPATH=src uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

Disposition: close `AFR-161`.
