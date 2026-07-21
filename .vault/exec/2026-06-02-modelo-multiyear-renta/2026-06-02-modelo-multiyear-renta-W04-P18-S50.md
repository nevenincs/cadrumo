---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S50'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M309 calculation-mode ad-hoc cuota-total enrollment test across two renta years

## Scope

- `src/aeat/application/calculations/tests/test_modelo_309_adhoc_fidelity.py`

## Description

- Rebaseline stale-open M309 enrollment-test row against the current test suite.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M309 fidelity test.
- Update the plan row to the actual calculation-mode M309 proof.

## Outcome

- `test_modelo_309_adhoc_fidelity.py` already proves calculation-mode M309 ad-hoc cuota-total continuity for 2024 and 2025.
- No product code changed in this step.

## Notes

- This is not a data-fidelity-only enrollment claim.
