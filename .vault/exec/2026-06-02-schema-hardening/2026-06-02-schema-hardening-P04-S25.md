---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S25'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# Assess formula runtime extraction boundaries

## Scope

- `src/aeat/domain/calculations/registry/_formula_runtime.py`

## Description

- Audit the current `_formula_runtime.py` responsibility clusters and
  working-tree diff.
- Identify staged extraction boundaries for expression evaluation,
  parameter lookup, M210 rate resolution, and previous-filing guards.
- Record public calculation API and M210 sentinel compatibility
  constraints.
- Define focused verification surfaces for future extraction commits.

## Outcome

- Completed as an audit-only slice. `_formula_runtime.py` had no local
  diff at audit time and remains unchanged by this step.
- The recommended first implementation slice is recursive expression
  evaluation and arithmetic/comparison dispatch behind `_formula_runtime.py`
  compatibility re-exports.
- Parameter/bracket lookup should move second, with public `read_parameter`
  preserved as a facade delegate.
- Initial-value and previous-filing guard extraction should wait until
  `_PreviousModeloSelector` ownership is settled by the binding resolver
  work.

## Notes

- No production code was edited, so no Python tests were run for this
  audit-only step.
- Vault checks and code-review logging were run before commit.
