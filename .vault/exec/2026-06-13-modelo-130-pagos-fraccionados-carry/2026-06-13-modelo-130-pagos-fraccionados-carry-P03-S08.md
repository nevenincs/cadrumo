---
tags:
  - '#exec'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S08'
related:
  - "[[2026-06-13-modelo-130-pagos-fraccionados-carry-plan]]"
---




# intersect the expanding-span candidate-quarter set with the periods for which a filing obligation actually existed, reading the operator-declared activity_start_date axis (the same field the deadline engine consumes for pre-alta suppression) so the alta-containing quarter is the first owed quarter and the span starts strictly after it, per the first-filer-attestation authority

## Scope

- `src/aeat/domain/calculations/registry/_bindings_previous_filing.py`

## Description

- Bound the casilla-05 pre-activity suppression to the already-landed first-filer activity-start axis rather than re-deriving an intersection in the selector: the carry registers standard cross-period requirements that flow through `partition_cross_period_requirements_by_activity_start` / `_period_strictly_before_activity_start` on `profile.activity_start_date`.
- Verified via a probe that a mid-year-alta (2T) filer 1T casilla-05 requirement is suppressed (period 1T end-date strictly before the declared alta), the alta-containing quarter staying in scope.

## Outcome

A first filer pre-alta prior-quarter casilla-05 requirement is suppressed to a provenance-marked no-prior-obligation zero through the landed first-filer machinery; no divergent intersection was added to `_bindings_previous_filing.py`. Verified by `test_modelo_130_casilla_05_carry.py` first-filer case (commit `53de169cb`).

## Notes

The ADR ratified the scoping at the application layer (not a selector facet), so the canonical mechanism is the first-filer partition; this step consumes it rather than duplicating it.
