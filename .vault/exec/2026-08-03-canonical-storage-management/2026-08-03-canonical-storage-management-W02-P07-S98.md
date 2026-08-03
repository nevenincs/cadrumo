---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:90f20cf1ebeb44ed78e1b3d7ad195b254e77e4311aec56b1b30046cbbbfd95c5'
step_id: 'S98'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Re-point the bundle export operation's root resolution onto effective_storage_root once S10 lands, deleting the inline override-or-settings-default duplicate, closing the cross-platform identity-comparison defect a relative or differently-cased override currently risks since only the reference body in the pointer transaction module normalises today

## Scope

- `src/cadrumo/application/user_profile/_bundle_export_operation.py`

## Description

- Confirm the bundle-export gating test suites are green (under their `integration` marker) before touching the file.
- Re-point `ProfileBundleExportJournalRepository.__init__`'s root resolution onto `effective_storage_root(storage_root, settings=settings)`, deleting the inline duplicate and the now-unused `load_settings` import.
- Confirm the export journal's `storage_root` (where journal state lives) is distinct from the operator-chosen bundle `destination`; the latter is untouched by this change, and production always constructs the repository with no override (`root=None`), so the normalisation change only activates on the explicit-override path exercised by tests.

## Outcome

Landed in commit `f8e0db04df`. Gated by `test_bundle_export.py` + `test_bundle_export_recovery.py` (30 tests total, green before and after; both files carry `pytest.mark.integration`, run with `-m integration`). Behaviour change: an explicit `storage_root` override was previously returned completely unnormalised, closing the cross-platform identity-comparison risk a relative or differently-cased override carried; it is now normalised through the shared accessor.

## Notes

None.
