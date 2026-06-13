---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S93'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W12.P23.S93` Profile Localization Fail-Closed Slice

Closed a focused profile repository hardening slice for S93 while continuing the broader secure-storage profile migration.

## Changes

- Replaced remaining operator-visible profile repository f-string errors with `tr()` keys for route mismatch, duplicate manifest registration, missing manifest, blank profile labels, and tombstoned profile selection.
- Added the new profile repository message keys to all shipped locale files through the locale catalog surface.
- Hardened duplicate tax-id enrollment so unreadable existing profile records fail closed with `UserProfileValidationError` and debug logging instead of being skipped.
- Added a real-behavior regression test that corrupts a persisted profile manifest, attempts a conflicting tax-id create, and proves no new profile is written.
- Cross-committed the intersecting stored-profile drift exception surface by binding `StoredProfileDriftError` to the central error registry, keeping its repair-oriented stored-data validation message key.
- Updated the roundtrip drift test to assert the typed `StoredProfileDriftError` boundary while preserving the underlying Pydantic validation exception for diagnostics.

## Validation

- `uv run pytest src/aeat/application/user_profile/test_profile_repository.py src/aeat/application/user_profile/test_aggregate.py src/aeat/application/user_profile/test_repository.py src/aeat/application/user_profile/test_repository_roundtrip.py src/aeat/core/errors/test_registry_enforcement.py -q` - 42 passed.
- `uv run ruff check src/aeat/application/user_profile/_profile_repository.py src/aeat/application/user_profile/test_profile_repository.py src/aeat/application/user_profile/test_repository_roundtrip.py src/aeat/core/errors/registry/_domain.py src/aeat/domain/user_profile/_errors.py src/aeat/domain/user_profile/__init__.py` - passed.
- `uv run python -m aeat.locales audit` - still reports the pre-existing extra key `errors.calc.bound_supplied_as_input` in `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`; this slice introduced no missing locale keys.
- `uv run vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` - still blocked by duplicate W07/W08 canonical identifiers around `P14` and `S56` through `S61`; per execution instruction this remains metadata debt, not a blocker for source hardening.

## Tracking

Completed internal tasklist for this slice:

- S93 profile repository localization inventory: complete.
- S93 duplicate tax-id fail-closed hardening: complete.
- S93 real-behavior regression coverage: complete.
- S93 intersecting stored-profile drift registry repair: complete.
- S93 focused gates and non-blocking debt capture: complete.

Next execution path:

- Continue migrating remaining profile and session storage surfaces onto sanctioned runtime helpers.
- Continue replacing user-facing raw exception text with `tr()` keys.
- Audit remaining broad exception handling for debug logging and fail-closed behavior.
- Reconcile the plan's duplicate W07/W08 canonical identifiers in a dedicated metadata slice.
