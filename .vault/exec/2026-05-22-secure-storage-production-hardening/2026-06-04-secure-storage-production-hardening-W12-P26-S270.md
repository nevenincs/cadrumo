---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S270'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s270-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S270`

Closed `AFR-168` for the user-profile secure-object repository runtime-default slice.

## Description

- Replaced raw profile and snapshot identifiers in repository miss, inner classification, and inner schema-version exception text with stable sanitized messages.
- Preserved profile id, snapshot id, bucket id, classification, and schema-version evidence in structured exception context for redacted diagnostic boundaries.
- Added repository-specific translation keys in every locale through `python -m aeat.locales`.
- Removed stale modelo work locale extras reported by the same canonical locale audit so the locale catalog returned to a clean state.
- Added real secure-object regression tests that persist mismatched inner envelopes and assert typed, translated, identifier-safe failures without mocks or duplicated repository logic.
- Closed `S270` through `vaultspec-core vault plan step check` and removed the generated plan `LINK RULES` block.

## Outcome

`AFR-168` is closed as `runtime-default`. The profile and snapshot repositories still bind to bucket-local secure-object storage, but user-facing failure strings no longer expose raw profile or snapshot identifiers when secure records are absent, misclassified, or written with unsupported inner schema versions.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/user_profile/_repository.py src/aeat/application/user_profile/test_repository.py src/aeat/application/user_profile/test_repository_anti_tautology.py src/aeat/application/user_profile/test_repository_roundtrip.py`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/test_repository.py src/aeat/application/user_profile/test_repository_anti_tautology.py src/aeat/application/user_profile/test_repository_roundtrip.py`
- `PYTHONPATH=src uv run --no-sync -q python -m aeat.locales audit`

## Notes

The locale CLI was run sequentially after an earlier parallel write race made the catalog briefly invalid. No manual locale content edits were needed after the catalog returned to a valid state.
The shared plan file also carried concurrent S273 and S393 ledger closures when staged; those plan-only closures are cross-committed with the regenerated `LINK RULES` block removed.
