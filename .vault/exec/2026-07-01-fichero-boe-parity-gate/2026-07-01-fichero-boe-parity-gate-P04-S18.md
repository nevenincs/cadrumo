---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S18'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

# Add an anti-tautology drift case mutating a rendered field number or order and asserting the gate panics

## Scope

- `src/aeat/application/filing/tests/test_fichero_boe_completeness_parity.py`

## Description

- Satisfied by the anti-tautology drift case in `test_export_completeness_gate.py` (P03): a complete Modelo 130 draft with one required-applicable casilla removed raises `FilingExportError`, names the dropped casilla, and writes no file. The test derives the dropped casilla from the live required-applicable set, so it fails if the gate ever stops firing.

## Outcome

Covered by the committed P03 gate test rather than duplicated in the P04 file, per DRY.

## Notes

Non-tautological: the expectation (a panic) is anchored in the manifest-vs-draft contract, not in registry output compared against itself.
