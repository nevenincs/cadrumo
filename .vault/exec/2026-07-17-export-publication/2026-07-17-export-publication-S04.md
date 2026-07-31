---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:48ad547ad9f002db76184ac94091cde02e35080901640f47e3c918b2e4cad17e'
step_id: 'S04'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

# Re-export the typed profile export service as the sole public export orchestration API

## Scope

- `src/cadrumo/application/user_profile/__init__.py`

## Description

- Extend the `user_profile` package facade in `__init__.py` to re-export the full typed export service as the sole public orchestration API.
- Add `PreparedProfileExport`, `ProfileBundleExportTarget`, `bundle_data_categories`, `prepare_profile_export`, `publish_prepared_export`, and `reconcile_prepared_exports` to the `TYPE_CHECKING` import block, the lazy `__getattr__` dispatch, and `__all__`, keeping `__all__` sorted for the ruff gate.

## Outcome

Cross-package consumers reach every export symbol through the package top-level facade; no consumer needs to dot into a private `_bundle_export*` submodule. Committed in `a9251f5fa2`.

## Notes

None.
