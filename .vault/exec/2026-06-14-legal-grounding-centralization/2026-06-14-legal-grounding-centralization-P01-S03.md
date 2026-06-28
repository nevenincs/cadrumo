---
tags:
  - '#exec'
  - '#legal-grounding-centralization'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S03'
related:
  - "[[2026-06-14-legal-grounding-centralization-plan]]"
---




# F2-interim: promote prorrata art.103.Dos (1.10) and art.9.1.c (50pp) thresholds to external_constants with legal_refs, value-identical

## Scope

- `src/aeat/domain/iva/_prorrata.py`

## Description

- Add two LIVA leaf constants to `core.external_constants`:
  `PRORRATA_ESPECIAL_MANDATORY_MULTIPLE = Decimal("1.10")` (art. 103.Dos) and
  `PRORRATA_SECTORAL_SEPARATION_SPREAD_PP = Decimal("50")` (art. 9.1.c), each grounded
  on Ley 37/1992 (BOE-A-1992-28740).
- Rewire `domain/iva/_prorrata.py`: `is_especial_mandatory` multiplies by the central
  `PRORRATA_ESPECIAL_MANDATORY_MULTIPLE`; the module-private
  `_SECTORAL_SEPARATION_THRESHOLD_PERCENTAGE_POINTS` now aliases
  `PRORRATA_SECTORAL_SEPARATION_SPREAD_PP`.

## Outcome

Value-identical centralization (1.10 / 50 unchanged). Threshold behaviour re-confirmed
by direct call (100 vs 90 → especial mandatory; 100 vs 91 → not); 40 prorrata tests
pass; `ruff` clean. These were the worst-grounded findings (ungrounded inline literals,
flagged by three independent agents) and now carry `legal_refs` grounding. F2-interim
closed; phase P01 (all three safe value-unchanged centralizations) complete.

## Notes

The prorrata subsystem is dormant (zero production callers — F2 in the audit). This
interim step centralizes its thresholds regardless of the eventual bind-or-delete
decision (P03 / F2-final): if the subsystem is later enrolled as a registry aggregation
source the constants are ready; if deleted, they are trivial to remove. Centralizing now
is safe and removes the ungrounded-literal class even before the routing decision.
