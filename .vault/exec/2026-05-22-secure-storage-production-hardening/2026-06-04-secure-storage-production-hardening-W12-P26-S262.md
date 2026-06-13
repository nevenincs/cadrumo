---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S262'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s262-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S262`

Closed `AFR-160` for the application user-profile package manifest.

## Description

- Audited `src/aeat/application/user_profile/__init__.py` as a manifest-discovery surface.
- Found the lazy resolver exported `UserProfileFact`, `UserProfileRecord`, and `UserProfileStatus` through `__getattr__` but omitted them from `__all__`.
- Added the missing domain profile record names to the package manifest.
- Added `record_to_path_values` to the typing-only projection import list so the typing surface matches the runtime lazy resolver.
- Added a public-surface regression test resolving the manifest names against the real domain package records.
- Removed the resolved `application/user_profile/__init__.py` drift cap from the cross-module import ratchet.
- Closed `S262` through `vaultspec-core vault plan step check` and manually aligned `AFR-160`.

## Outcome

`AFR-160` is closed. The application user-profile package manifest now matches the lazy namespace for domain profile records, and the ratchet baseline locks in the removed `__all__` drift.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/user_profile/__init__.py src/aeat/application/user_profile/test_bundle_reexports.py src/aeat/tests/test_cross_module_imports_resolve.py`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/test_bundle_reexports.py src/aeat/application/user_profile/test_lazy_boundary.py`

Validation caveat:

- `uv run --no-sync pytest -q src/aeat/tests/test_cross_module_imports_resolve.py` still fails for unrelated current regressions in `src/aeat/application/modelo/_taxation_comparison.py`, `src/aeat/domain/contribuyente/assets/__init__.py`, and `src/aeat/domain/contribuyente/inventory/__init__.py`.

## Notes

The plan check still reports the existing `PLAN022` monotonic-order warning only.
