---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S15'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

# Add an offline fichero-BOE parity test asserting required-applicable casillas reach disk across export-capable covered modelos

## Scope

- `src/aeat/application/filing/tests/test_fichero_boe_completeness_parity.py`

## Description

- Add `test_fichero_boe_completeness_parity.py`: parametrized over the fixed-width covered modelos with a manifest and a reusable complete draft (130, 111, 115, 123), asserting `required_applicable ⊆ rendered` (every required, representable casilla reaches disk) and that the complete draft exports clean.

## Outcome

Landed in commit `e616666ad`. Eight tests pass (four modelos x two assertions). Also asserts `required_applicable` is non-empty per modelo, so the gate cannot pass vacuously.

## Notes

Modelos 303/200 have manifests but no reusable complete-draft builder in the shared support module; the four covered here plus the 303 suppression case (P02) and the 130 drift case (P03) exercise the gate across the representative shapes.
