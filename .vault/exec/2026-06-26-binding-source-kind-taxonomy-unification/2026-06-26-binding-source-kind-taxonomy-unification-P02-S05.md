---
tags:
  - '#exec'
  - '#binding-source-kind-taxonomy-unification'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S05'
related:
  - "[[2026-06-26-binding-source-kind-taxonomy-unification-plan]]"
---

# Re-type the five ledger and retenciones resolver owned_sources to enum members (sequenced after #6 P03 + #28 land on this mesh surface)

## Scope

- `src/aeat/application/aggregation/_modelo_bindings.py`

## Description

- Reconcile `P02.S05` as the `_modelo_bindings.py` resolver re-typing row.
- Record the original landing in `3f78cccf50`: re-type the five ledger and
  retenciones resolver `owned_sources` class attributes to `BindingSourceKind`
  members.
- Confirm the current tree still exposes those resolver `owned_sources` as typed
  tuples of `BindingSourceKind` members.

## Outcome

The checked row now has its own exec record. The existing P02 evidence records
S05 landed after the active retenciones WIP and that the P02 mesh / boundary and
parity gates were green.

## Notes

No code changed in this reconciliation. The original landing used the
apply-cached gated drive to avoid overwriting peer WIP.
