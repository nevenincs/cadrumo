---
tags:
  - '#exec'
  - '#registry-suite-red-at-head'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:eec339519c83b9a19cd5842360f765d92781814f23b64e76a8126f262d050fba'
step_id: 'S03'
related:
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---
# Guard every declared-category base-only flow against deduction authority

## Scope

- `src/cadrumo/application/aggregation/tests/test_supplier_side_reverse_charge_reaches_casilla_122.py`

## Description

Added a count-free property test over the production
`_DECLARED_CATEGORY_BASE_ONLY_FLOWS` mapping. Every mapped flow is checked with
the canonical `is_deducible_flow` predicate, so a future member that would
trigger the observation model's deduction-authority refusal fails immediately.

## Outcome

The complete owning module passes nine tests. Ruff and BasedPyright are clean,
and `git diff --check` reports no defect. The test imports the production table
and canonical predicate; it does not restate the table, mirror the deduction
flow set, or use a fake, mock, patch, skip, or compatibility route.

## Notes

The existing real invoice tests remain the behavioral proof that the two current
categories reach their distinct Modelo 303 casillas. This property is the
structural complement that makes future additions fail before an output row is
accidentally routed onto a deduction-only flow.
