---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S60'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M232 related-party data-fidelity enrollment test proving NIF continuity, distinct importes, and threshold coverage

## Scope

- `src/aeat/application/calculations/tests/test_modelo_232_operaciones_vinculadas_fidelity.py`

## Description

- Rebaseline stale-open M232 data-fidelity row against the current test suite.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M232 fidelity test.
- Update the plan row to the actual M232 related-party fidelity proof.

## Outcome

- `test_modelo_232_operaciones_vinculadas_fidelity.py` already proves related-party data-fidelity, NIF identity continuity, distinct importes, and threshold coverage across 2024 and 2025.
- No product code changed in this step.

## Notes

- This does not claim a calculation engine for M232.
