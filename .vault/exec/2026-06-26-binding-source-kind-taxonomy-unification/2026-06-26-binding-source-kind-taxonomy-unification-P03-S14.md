---
tags:
  - '#exec'
  - '#binding-source-kind-taxonomy-unification'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S14'
related:
  - "[[2026-06-26-binding-source-kind-taxonomy-unification-plan]]"
---

# Migrate the per-modelo aggregation service and registry-provider consumers off AggregationSourceKind and delete it

## Scope

- `src/aeat/application/aggregation/_service.py`

## Description

- Reconcile `P03.S14` as the `AggregationSourceKind` retirement row.
- Record the original landing in `b5b28a86aa`: delete `AggregationSourceKind`,
  inline the four corresponding `BindingSourceKind` values, and migrate the
  per-modelo aggregation service, registry-provider tables, review/operator
  helpers, ledger manual actions, re-exports, and affected tests.
- Confirm the current tree has no `class AggregationSourceKind` definition and
  the per-modelo aggregation service consumes `BindingSourceKind`.

## Outcome

The checked row now has its own exec record. The existing P03 evidence records
the duplicate-enum deletion complete with 1032 targeted tests green, registry
loads clean, both parity halves green, and clean collection.

## Notes

No code changed in this reconciliation. Historical docstrings may mention the
retired enum by name; there is no live class definition.
