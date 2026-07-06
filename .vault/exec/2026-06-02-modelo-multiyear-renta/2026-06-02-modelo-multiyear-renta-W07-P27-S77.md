---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S77'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# write the M347 data-fidelity E2E test asserting year-over-year fidelity and provenance roundtrip of operaciones-con-terceros across two renta years via real adapters (vaultspec-standard-executor)

## Scope

- `src/aeat/application/calculations/test_modelo_347_fidelity_continuity.py`

## Description

- Rebaseline the M347 data-fidelity enrollment against the live test tree.
- Confirm `test_modelo_347_informativa_fidelity.py` persists and reloads two renta-year counterparty observations through the real repository.
- Close the stale-open E2E row without changing source code.

## Outcome

Closed as current-code satisfied. The current M347 test proves year-over-year fidelity, provenance roundtrip, and counterparty identity continuity.

## Notes

Verification: the focused W06/W07 stale-open test batch returned 42 passed.
