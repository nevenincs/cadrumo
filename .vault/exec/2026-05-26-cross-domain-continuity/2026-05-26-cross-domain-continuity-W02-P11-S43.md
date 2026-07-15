---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S43'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# confirm _MODELO_APPLICABILITY_RULES is the canonical modelo-level applicability authority

## Scope

- `add module docstring documenting that modelo-level rules live in Python while window-level applicability_conditions live on ModeloDeadlineWindow registry slot`
- `audit the 18 modelos to ensure every rule populates applicable_entity_types required_income_categories required_estimation_regimes and required_payer_fact where the modelo demands those axes`
- `src/aeat/domain/calculations/registry/_applicability.py`

## Description

- Reconciled the applicability authority documentation to the Wave-2 review.
- Confirmed `acea52801e` supplied the reviewed implementation.
- Added this per-step execution record without changing production sources.

## Outcome

The 2026-05-29 review accepted the implementation. This record restores the one-Step, one-record traceability edge.

## Notes

The same reviewed commit also supports S44 and S46; each row receives its own record.
