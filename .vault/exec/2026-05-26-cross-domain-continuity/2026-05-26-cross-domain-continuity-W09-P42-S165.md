---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S165'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---




# merge active_bucket_id_or_raise and require_active_bucket_id into one canonical function update all call sites

## Scope

- `src/aeat/application/workflow/_models.py`

## Description

Consolidated `active_bucket_id_or_raise` and
`require_active_bucket_id` into a single canonical function in
`src/aeat/application/workflow/_models.py`. The two functions had
literally identical bodies; their docstrings carried different
audience notes which are merged into the canonical
`require_active_bucket_id` docstring.

Deleted `active_bucket_id_or_raise`; promoted
`require_active_bucket_id` to the package surface
(`application.workflow.__init__` re-export + __all__ entry).

Migrated 6 consumer files
(`application/review/_operator.py`,
`entrypoints/cli/_app_live.py`, `_common.py`, `_ledger.py`,
`_modelo.py`, and `test_ledger_exception_propagation.py`) from
the deleted alias to the canonical via a bulk-text rewrite.

## Outcome

15 workflow tests
(`test_active_profile_resolution.py` 4 + `test_models.py` 11) pass
after the consolidation. Import surface verified:
`from aeat.application.workflow import require_active_bucket_id`
resolves to the same function as the direct `_models` import.

## Notes

Real refactor. No shim re-export of the deleted name (per the
no-shims rule). Wave-1 drift sweep DUPLICATE finding closed.
