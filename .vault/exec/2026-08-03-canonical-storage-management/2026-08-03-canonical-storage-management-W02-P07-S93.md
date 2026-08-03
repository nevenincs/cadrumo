---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:32e06bb33734fa240870ba28d70d05173cb6b20b98f287e1ff40378c6e35ec0c'
step_id: 'S93'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Re-point the profile pointer transaction module onto effective_storage_root once S10 lands, using it as the reference body for the new primitive since it is the only one of the six duplicate sites that already normalises via expanduser and resolve

## Scope

- `src/cadrumo/application/user_profile/_profile_pointer_transaction.py`

## Description

- Confirm the pointer-transaction module's gating test suite is green before touching the file.
- Re-point `_canonical_root` onto `effective_storage_root(root)`, deleting its inline `expanduser().resolve(strict=False)` normalisation and the now-unused `load_settings` import.
- Re-run the gating suite and the broader `user_profile` package.

## Outcome

Landed in commit `517d6e2611`. Gated by `test_orchestration_pointer.py` (5 tests, green before and after) and the full `application/user_profile` package (367 tests, green after). Behaviour change: a relative root override previously resolved against the process's current working directory via bare `Path.resolve()`; it now anchors under the platform user-data root, matching every other relative operator path in the codebase.

## Notes

None.
