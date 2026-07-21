---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S84'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# write the M036 obligation-continuity E2E test asserting the censo obligation-set carries across alta year N and modificacion year N+1 via real adapters (vaultspec-standard-executor)

## Scope

- `src/aeat/application/calculations/test_modelo_036_obligation_continuity.py`

## Description

- Rebaseline the M036 censal continuity enrollment against the live test tree.
- Confirm `test_modelo_036_censal_continuity.py` persists alta and modificacion annual contexts for 2025 and 2026 through the real repository.
- Close the stale-open E2E row without changing source code.

## Outcome

Closed as current-code satisfied. The current M036 test proves obligation-set continuity, identity continuity, and event-kind isolation across two annual contexts.

## Notes

Verification: the focused W06/W07 stale-open test batch returned 42 passed.
