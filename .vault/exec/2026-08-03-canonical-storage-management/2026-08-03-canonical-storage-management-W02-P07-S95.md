---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:ac07e2660d02e7799f6d2a932d84636a6907f5876c10f7ee914332223f2ad320'
step_id: 'S95'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Re-point the profile bucket scan module's root resolver onto effective_storage_root once S10 lands, deleting the local override-or-settings-default duplicate

## Scope

- `src/cadrumo/application/workflow/_profile_bucket_scan.py`

## Description

- Confirm the profile-bucket-scan gating test suite is green before touching the file.
- Re-point `_resolve_root` onto `effective_storage_root(root)`, deleting its inline unnormalised override pass-through and its function-local `load_settings` import.
- Promote the `effective_storage_root` import to module top level (no circular-import risk from a leaf `core.paths` import) and re-run the gating suite plus the full `workflow` package.

## Outcome

Landed in commit `132c801008`. Gated by `test_profile_bucket_scan.py` (8 tests, green before and after) and the full `application/workflow` package (100 tests, green after). Behaviour change: an explicit root override was previously returned completely unnormalised (no `expanduser`, no anchored `resolve` of a relative path); it is now normalised through the shared accessor.

## Notes

None.
