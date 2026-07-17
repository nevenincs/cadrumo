---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S48'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M308 ad-hoc data-fidelity enrollment test proving two-renta encrypted observation roundtrip

## Scope

- `src/aeat/application/calculations/tests/test_modelo_308_adhoc_fidelity.py`

## Description

- Rebaseline stale-open M308 data-fidelity row against the current test suite.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M308 fidelity test.
- Update the plan row to the actual M308 two-year fidelity proof.

## Outcome

- `test_modelo_308_adhoc_fidelity.py` already proves ad-hoc M308 data-fidelity roundtrip for 2024 and 2025.
- No product code changed in this step.

## Notes

- This does not claim a numeric refund oracle.
