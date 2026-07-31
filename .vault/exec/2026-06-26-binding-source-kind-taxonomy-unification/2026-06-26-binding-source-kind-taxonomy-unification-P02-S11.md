---
tags:
  - '#exec'
  - '#binding-source-kind-taxonomy-unification'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:2b11e5258d974a949ecfb308ed0b2ddb253a8f5bd370f5cc866e60a47fc5efdc'
step_id: 'S11'
related:
  - "[[2026-06-26-binding-source-kind-taxonomy-unification-plan]]"
---

# Re-type the borrador resolver owned_sources to an enum member

## Scope

- `src/aeat/application/modelo/_borrador_binding.py`

## Description

- Reconcile `P02.S11` as the borrador resolver re-typing row.
- Record the original landing in `1200e05329`: re-type
  `Modelo100BorradorSourceResolver.owned_sources` to the
  `BindingSourceKind.BORRADOR` member.
- Confirm the current resolver still declares `owned_sources` as a
  `tuple[BindingSourceKind, ...]`.

## Outcome

The checked row now has its own exec record. The existing P02 evidence records
S06 through S12 landed together and that both parity halves and mesh / boundary
suites were green.

## Notes

No code changed in this reconciliation.
