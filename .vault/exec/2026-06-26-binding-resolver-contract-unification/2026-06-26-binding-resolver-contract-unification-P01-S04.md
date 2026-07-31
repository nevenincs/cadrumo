---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:4e60f6734ff0d713fd3e672991b9ce6198a1c13dda3adce70f91139a021b9b25'
step_id: 'S04'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---

# Drop the deleted envelopes from the aggregation package __all__ and lazy __getattr__ re-export surface in the same commits that delete them

## Scope

- `src/aeat/application/aggregation/__init__.py`

## Description

Commit `52edec4b1`. Dropped the deleted M349-only
`PerModeloRegistryBindingResolution` / `resolve_per_modelo_registry_binding_values`
surface from the aggregation package exports in the same atomic deletion commit
that removed the vestigial `_registry_provider` module.

## Outcome

P01.S04 complete. The package facade no longer advertises the deleted envelope or
resolver helper; the remaining aggregation exports stay intact and the live
registry-binding mesh path remains the production route for M349 counterpart values.

## Notes

This record reconciles the plan alert only. The landed code change was already
covered by `52edec4b1` and summarized in the existing S02 record, but
`plan-closure-requires-exec-records` requires a dedicated S04 record.
