---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S79'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# write the M184 data-fidelity E2E test building atribucion-de-rentas member RegistryModeloObservation rows directly and asserting year-over-year fidelity across two renta years (vaultspec-standard-executor)

## Scope

- `src/aeat/application/calculations/test_modelo_184_fidelity_continuity.py`

## Description

- Rebaseline the M184 data-fidelity enrollment against the live test tree.
- Confirm `test_modelo_184_informativa_fidelity.py` persists member attribution observations for 2024 and 2025 through the real repository.
- Close the stale-open E2E row without changing source code.

## Outcome

Closed as current-code satisfied. The current M184 test proves member identity continuity, attribution amount isolation, and encrypted-SQL roundtrip fidelity.

## Notes

Verification: the focused W06/W07 stale-open test batch returned 42 passed.
