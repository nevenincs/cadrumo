---
tags:
  - '#exec'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:4065e7ec803a90860fb3aed5fc6d95b798e798a811e964fa356b25606ae6a0d7'
step_id: 'S122'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---
# Reconcile the live two-drift-direction deferred-edge declaration: remove the 26 stale rows, classify the 8 undeclared live edges with checked site-specific rationale, and retire the generic _DECLARED aggregate in favour of PINNED_DEFERRED_CROSS_LAYER_IMPORTS, since the existing undeclared and stale tests correctly failed in both directions (Terra xhigh fixes and refactors)

## Scope

- `src/cadrumo/tests/`

## Changes

- `M` `src/cadrumo/tests/test_deferred_cross_layer_imports.py`
- `verify:` `uv run --no-sync pytest -q -n 0 -m "unit or (integration and not serial)" src/cadrumo/tests/test_deferred_cross_layer_imports.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/tests/test_deferred_cross_layer_imports.py` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/tests/test_deferred_cross_layer_imports.py` -> `pass`

## Notes

The plan premise was corrected before execution: both drift tests have existed since 2026-08-10 and had correctly failed in opposite directions. The repair removed 26 stale rows and replaced the generic `_DECLARED` aggregate with the checked `PINNED_DEFERRED_CROSS_LAYER_IMPORTS` declaration. A module-level graph probe found no cycles for the eight live additions. They are not hidden layer violations because the governing contract explicitly permits application-to-persistence and application-to-outbound construction edges, so each was recorded as a site-rationalized `DELIBERATE_DEMAND_LOAD` rather than mislabeled `UNADJUDICATED`.
