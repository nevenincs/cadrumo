---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S238'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s238-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S238`

Closed `AFR-136` for the modelo profile binding resolver.

## Description

- Reviewed `src/aeat/application/modelo/_profile_binding.py` as a profile-backed
  manifest discovery resolver over the active bucket's user-profile lifecycle
  repository.
- Verified the module does not own durable storage, construct direct SQL routes,
  read naked environment variables, write plaintext side stores, or mutate
  profile state.
- Found API consistency and privacy hardening work in its refusal paths:
  `ProfileBindingResolutionError` raised raw strings and the string-to-decimal
  parse path could expose the raw profile fact value in operator-facing errors.
- Added stable locale keys and structured context for profile-binding trace,
  decimal, date, and enum-channel refusals.
- Changed the profile-binding decimal parse wrapper to discard the shared
  parser's raw-value message and emit a sanitized refusal that includes only the
  binding id and value type.
- Extended real resolver tests to assert localized metadata and prove the raw
  invalid profile fact string is not echoed.
- Closed `S238` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-136` is closed as `manifest-discovery`. No storage migration was required:
profile records remain owned by the user-profile lifecycle repository, and the
resolver only projects profile facts into calculation binding channels. The API
surface is now stricter: user-facing refusals carry stable locale keys and
structured context, and profile fact values are not leaked from decimal parse
failures.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/modelo/_profile_binding.py src/aeat/application/modelo/test_profile_binding.py`
- `uv run --no-sync pytest -q src/aeat/application/modelo/test_profile_binding.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Notes

Locale files were already a shared staged surface in this worktree. This step
intentionally cross-commits the locale catalog entries required by the new
profile-binding `translated_message` keys while excluding unrelated staged
export/test artifacts.
