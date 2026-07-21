---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S46'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M349 intracomunitario data-fidelity enrollment test proving encrypted observation roundtrip and year isolation

## Scope

- `src/aeat/application/calculations/tests/test_modelo_349_intracomunitario_fidelity.py`

## Description

- Rebaseline stale-open M349 data-fidelity row against the current test suite.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M349 fidelity test.
- Update the plan row to the actual M349 two-year fidelity proof.

## Outcome

- `test_modelo_349_intracomunitario_fidelity.py` already proves encrypted observation roundtrip and year isolation for 2024 and 2025 intracomunitario data.
- No product code changed in this step.

## Notes

- This is a data-fidelity closure, not a numeric calculation proof.
