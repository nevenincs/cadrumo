---
tags:
  - '#exec'
  - '#binding-source-kind-taxonomy-unification'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S09'
related:
  - "[[2026-06-26-binding-source-kind-taxonomy-unification-plan]]"
---

# Re-type the previous-filing resolver owned_sources to an enum member

## Scope

- `src/aeat/application/calculations/_multi_year.py`

## Description

- Reconcile `P02.S09` as the previous-filing resolver re-typing row.
- Record the original landing in `1200e05329`: re-type
  `PreviousFilingSourceResolver.owned_sources` to the
  `BindingSourceKind.PREVIOUS_FILING` member.
- Confirm the current resolver still declares `owned_sources` as a
  `tuple[BindingSourceKind, ...]`.

## Outcome

The checked row now has its own exec record. The existing P02 evidence records
S06 through S12 landed together and that both parity halves and mesh / boundary
suites were green.

## Notes

No code changed in this reconciliation.
