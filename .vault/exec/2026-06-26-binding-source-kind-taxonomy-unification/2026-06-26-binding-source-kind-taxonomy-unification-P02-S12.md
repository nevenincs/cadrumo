---
tags:
  - '#exec'
  - '#binding-source-kind-taxonomy-unification'
date: '2026-07-05'
modified: '2026-07-08'
step_id: 'S12'
related:
  - "[[2026-06-26-binding-source-kind-taxonomy-unification-plan]]"
---

# Re-type the invoice-catalogue resolver owned_sources to enum members

## Scope

- `src/aeat/application/invoices/_source_resolver.py`

## Description

- Reconcile `P02.S12` as the invoice-catalogue resolver re-typing row.
- Record the original landing in `1200e05329`: re-type the invoice-catalogue
  resolver owned set to `BindingSourceKind.COLLECTIBLE_INVOICE` and
  `BindingSourceKind.PAYABLE_INVOICE` members.
- Confirm the current resolver still declares `_OWNED_SOURCES` and
  `owned_sources` as `tuple[BindingSourceKind, ...]`.

## Outcome

The checked row now has its own exec record. The existing P02 evidence records
S06 through S12 landed together and that both parity halves and mesh / boundary
suites were green.

## Notes

No code changed in this reconciliation.
