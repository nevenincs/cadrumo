---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S263'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s263-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S263`

Closed `AFR-161` for the profile aggregate storage boundary.

## Description

- Audited `src/aeat/application/user_profile/_aggregate.py` as the in-memory cross-store projection over active-profile, manifest, SQL, and remote storage surfaces.
- Found aggregate mismatch validators embedded raw profile IDs and operator labels in validation error text.
- Added a local aggregate Pydantic config extending the shared strict frozen config with hidden validation inputs.
- Routed aggregate mismatch failures through sanitized `UserProfileValidationError` construction with non-sensitive context.
- Added literal `translated_message` keys so `aeat.locales` can discover the new user-facing messages.
- Added regression assertions proving rendered `ValidationError` output does not contain profile IDs or labels.
- Added localized strings through `python -m aeat.locales`.
- Closed `S263` through `vaultspec-core vault plan step check` and manually aligned `AFR-161`.

## Outcome

`AFR-161` is closed. Aggregate cross-store inconsistency still fails fast, but rendered validation errors no longer echo raw profile identifiers or display labels, and the user-facing message path is enrolled in the locale audit.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/user_profile/_aggregate.py src/aeat/application/user_profile/test_aggregate.py`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/test_aggregate.py`
- `PYTHONPATH=src uv run --no-sync -q python -m aeat.locales audit`

## Notes

The plan check still reports the existing `PLAN022` monotonic-order warning only.
