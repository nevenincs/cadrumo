---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S20'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# Assess binding resolver extraction boundaries

## Scope

- `src/aeat/domain/calculations/registry/_bindings.py`

## Description

- Audit the current `_bindings.py` resolver families and working-tree
  diff before editing.
- Identify extraction boundaries for binding resolver families without
  changing code or schema semantics.
- Record the shared-worktree blocker around previous-filing peer WIP.
- Define the next safe extraction order and verification surfaces.

## Outcome

- Completed as an audit-only slice. `_bindings.py` remains unchanged by
  this step because the file contains active peer feature WIP around
  `per_grupo_member` previous-filing aggregation.
- The recommended next implementation slice is a low-coupling row-set
  extraction covering related-party, foreign-asset, attribution, and
  refund row resolvers behind `_bindings.py` compatibility re-exports.
- Previous-filing extraction is intentionally deferred until the active
  same-period group-member work lands and the `_formula_runtime.py`
  dependency on `_PreviousModeloSelector` is preserved or retired.

## Notes

- No production code was edited, so no Python tests were run for this
  audit-only step.
- Vault checks were run after the audit was recorded; see the commit for
  the exact command outcomes.
