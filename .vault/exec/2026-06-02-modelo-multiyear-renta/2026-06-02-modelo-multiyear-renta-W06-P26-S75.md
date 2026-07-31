---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:4f1fc218390d0a83a0284e33d51042ccf6e69b60b3634ed4c2f9e5c8b2a33071'
step_id: 'S75'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# write the M151 >=2-renta E2E test asserting the flat-rate calculation across two renta years via real adapters (vaultspec-high-executor)

## Scope

- `src/aeat/application/calculations/test_modelo_151_flat_rate_continuity.py`

## Description

- Rebaseline the M151 two-renta enrollment test against the live test tree.
- Confirm `test_modelo_151_beckham_cuota_continuity.py` records 2024 and 2025 through the calculation recorder.
- Close the stale-open E2E row without changing source code.

## Outcome

Closed as current-code satisfied. The current test is the real-adapter M151 flat-rate calculation enrollment for two renta years.

## Notes

Verification: the focused W06/W07 stale-open test batch returned 42 passed.
