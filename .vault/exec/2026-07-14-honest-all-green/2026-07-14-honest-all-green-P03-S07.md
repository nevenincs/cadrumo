---
tags:
  - '#exec'
  - '#honest-all-green'
date: '2026-07-14'
modified: '2026-07-17'
body_hash: 'sha256:6ab886c8f0c675ef259e5895d18aa27b1b994f7267675414e3d212b82bc975b4'
step_id: 'S07'
related:
  - "[[2026-07-14-honest-all-green-plan]]"
---

# Fix the aggregation source-resolver enrollment and precedence-ladder failures

## Scope

- `src/cadrumo/application/aggregation`

## Description

- Re-ran the three failing aggregation gates sequentially at HEAD to confirm the signatures and rule out a parallel race.
- Traced the root cause: a peer landed the `LedgerIrnrIncomeAggregationSourceResolver` (M210 IRNR income ledger aggregation) fully wired into the live `merge_source_resolutions` mesh tuple in `_calculation_actions.py` and correctly placed its `LEDGER_IRNR_INCOME_AGGREGATION` source kind in the `deterministic_lock` tier of `CALLER_OVERRIDE_PRECEDENCE_LADDER`, but did not update the two conformance-gate inventories that pin the enrolled surface.
- Confirmed the resolver is genuinely live (constructed unconditionally in the mesh; its `resolve` gates on `_revision_has_binding_source`) and correctly dispositioned (a deterministic ledger aggregation, LOCK, consistent with every sibling `LEDGER_*_AGGREGATION` kind).
- Recorded the genuinely-enrolled twentieth resolver in `test_source_resolver_enrollment.py`: added the resolver qualname to `_ENROLLED_SOURCE_MESH_RESOLVERS` and updated the wired/total counts in both docstrings (16 wired to 17, 19 total to 20).
- Added `LEDGER_IRNR_INCOME_AGGREGATION` to the frozen LOCK behavioural-anchor set in `test_precedence_ladder_conformance.py`.

## Outcome

All nine aggregation gate tests pass sequentially (`-n 0`): `test_precedence_ladder_conformance.py` (5) and `test_source_resolver_enrollment.py` (4). Ruff clean on both files. This is the gate operating exactly as designed - a new live resolver failed the pin loudly, and the honest resolution (matching the gate's own error instruction) was to record the enrolled resolver in the inventory, not to mute it. No production code changed; the resolver was already correctly enrolled and dispositioned.

## Notes

The two modified test files sit beside two peer WIP files in the same package (`test_iva_ledger.py`, `test_renta_ledger.py`) carrying a cosmetic issue-number comment sweep, and `_calculation_actions.py` carries the same cosmetic sweep uncommitted; none of that WIP touches the enrollment tuple or the ladder, so there was no collision. Committed with an explicit pathspec naming only the two files authored here.
