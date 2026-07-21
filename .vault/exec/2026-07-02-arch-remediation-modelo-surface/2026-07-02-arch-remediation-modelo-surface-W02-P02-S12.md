---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S12'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

# Consume the same declaration from the calculate orchestrator and delete the function-local MODELO_303_IVA_COMPENSATION_BINDING_ID import and the previous-filing exclusion shim

## Scope

- `src/aeat/application/modelo/_calculation_actions.py`

## Description

- Import the canonical id + set at the orchestrator module top; delete the three function-local `MODELO_303_IVA_COMPENSATION_BINDING_ID` imports.
- Return the canonical set from `_iva_compensation_previous_filing_exclusions` instead of rebuilding it.
- Drop the redundant application re-export; its one consumer reads the domain facade.

## Outcome

The calculate orchestrator consumes the same declaration as the validator; no function-local import or rebuilt exclusion set remains. Commit `e353111d8`.

## Notes
