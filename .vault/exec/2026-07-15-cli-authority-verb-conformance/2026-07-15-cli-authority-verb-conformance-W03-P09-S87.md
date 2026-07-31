---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:1baa662baa8fddcee87a62ae4ae43c6533007c503ced18b0a3f5ca113cec4111'
step_id: 'S87'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Re-export the typed profile export service as the sole public export orchestration API

## Scope

- `src/cadrumo/application/user_profile/__init__.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD rather than a fresh edit. The predecessor profile-export-consolidation campaign landed the re-export surface in commit `a9251f5fa2`.

- Add the lazy `__getattr__` (PEP 562) dispatch-table entries `("._bundle_export", (...))` and `("._bundle_export_operation", ("ProfileBundleExportJournalRepository",))`, mirroring every module-level symbol the package already lazily re-exports.
- List every publication-facing name under the `._bundle_export` entry: `PreparedProfileExport`, `ProfileBundleExportPurpose`, `ProfileBundleExportReconcileFailure`, `ProfileBundleExportReconciliation`, `ProfileBundleExportRequest`, `ProfileBundleExportResult`, `ProfileBundleExportTarget`, `ProfileBundleExportTransport`, `bundle_data_categories`, `bundle_excluded_data_categories`, `export_profile_bundle`, `prepare_profile_export`, `publish_prepared_export`, `reconcile_prepared_exports`.
- Add the matching `TYPE_CHECKING`-guarded static import block so type checkers resolve the same names without paying the eager-import cost the package's existing lazy-facade convention avoids.

## Outcome

`export_profile_bundle` and its typed contracts are reachable only through `cadrumo.application.user_profile`'s public facade; no cross-package consumer needs to, or does, import `._bundle_export` or `._bundle_export_operation` directly.

Verified against HEAD by reading the dispatch table at `src/cadrumo/application/user_profile/__init__.py:335-357` and confirming both CLI consumers (`entrypoints/cli/_config/_profile_bundle.py`, the portable-export and subject-access-request commands) import `export_profile_bundle` and its request/purpose/transport types from `....application.user_profile`, not from a private submodule. Gate: `uv run --no-sync pytest src/cadrumo/application/user_profile/tests/test_bundle_export.py src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py -m "" -q` reports 29 passed.

## Notes

None.
