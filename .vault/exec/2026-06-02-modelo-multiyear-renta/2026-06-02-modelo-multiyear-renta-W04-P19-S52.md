---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S52'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M360 ad-hoc refund-request data-fidelity enrollment test proving two-renta roundtrip and estado-miembro isolation

## Scope

- `src/aeat/application/calculations/tests/test_modelo_360_adhoc_fidelity.py`

## Description

- Rebaseline stale-open M360 data-fidelity row against the current test suite.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M360 fidelity test.
- Update the plan row to the actual M360 two-year fidelity proof.

## Outcome

- `test_modelo_360_adhoc_fidelity.py` already proves M360 refund-request data-fidelity and estado-miembro isolation for 2024 and 2025.
- No product code changed in this step.

## Notes

- This is a fidelity and isolation proof, not a numeric refund oracle.
