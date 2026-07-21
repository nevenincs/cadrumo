---
tags:
  - '#exec'
  - '#binding-source-kind-taxonomy-unification'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-06-26-binding-source-kind-taxonomy-unification-plan]]"
---

# Re-type DEFERRED_SOURCE_KINDS and _BUCKET_AGGREGATION_OWNED_SOURCES to frozenset of BindingSourceKind

## Scope

- `src/aeat/application/modelo/_calculation_actions.py`

## Description

- Reconcile `P02.S04` as the mesh-set re-typing row that was absorbed by a
  concurrent codex commit during P02.
- Record the historical intent: move the deferred and bucket-aggregation source
  sets off bare strings and onto `frozenset[BindingSourceKind]`.
- Re-check the current tree after later refactors: the policy surface now
  projects `BUCKET_AGGREGATION_OWNED_SOURCES`, `BUCKET_AGGREGATION_LOCK_SOURCES`,
  `CALLER_OVERRIDABLE_CARRY_SOURCES`, and `DEFERRED_SOURCE_KINDS` as typed
  `BindingSourceKind` sets consumed by `_calculation_actions.py`.

## Outcome

The checked row now has its own exec record. The existing P02 evidence records
the phase complete with both parity halves green, mesh / boundary suites green,
and clean `src/aeat` collection.

## Notes

No code changed in this reconciliation. The live tree has progressed since the
original row: the typed source policy is now factored through
`_calculation_source_policy.py`, while `_calculation_actions.py` still consumes
the typed constants.
