---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S39'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M322 two-renta REGE individual calculation enrollment test for December 2025 and 2026

## Scope

- `src/aeat/application/calculations/tests/test_modelo_322_grupo_individual_continuity.py`

## Description

- Rebaseline stale-open M322 enrollment-test row against the current test suite.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M322 continuity test.
- Update the plan row to the actual M322 REGE calculation enrollment proof.

## Outcome

- `test_modelo_322_grupo_individual_continuity.py` already proves real M322 monthly REGE calculation for December 2025 and December 2026.
- No product code changed in this step.

## Notes

- This does not claim a cross-period carry; the landed proof is year-stable calculation continuity.
