---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:d6cc7a4511f598b12c64a12a6c36f938fb463dc5622431ed833f93e843feeaef'
step_id: 'S96'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Re-point the profile repository's root resolution onto effective_storage_root once S10 lands, deleting the inline override-or-settings-default duplicate

## Scope

- `src/cadrumo/application/user_profile/_profile_repository.py`

## Description

- Confirm the `ProfileRepository` gating test suite is green before touching the file.
- Re-point `ProfileRepository.__init__`'s root resolution onto `effective_storage_root(root)`, deleting the inline `root if root is not None else load_settings()....` duplicate and the now-unused `load_settings` import.
- Re-run the gating suite and the full `user_profile` package.

## Outcome

Landed in commit `431a3a04b1`. Gated by `test_profile_repository.py` (31 tests, green before and after) and the full `application/user_profile` package (367 tests, green after). Behaviour change: an explicit root override was previously returned completely unnormalised; it is now normalised through the shared accessor.

## Notes

None.
