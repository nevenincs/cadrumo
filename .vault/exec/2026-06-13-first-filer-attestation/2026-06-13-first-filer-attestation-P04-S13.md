---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S13'
related:
  - "[[2026-06-13-first-filer-attestation-plan]]"
---




# Add a real-storage test proving the alta-containing period stays in scope as the first obligation and is NOT suppressed

## Scope

- `src/aeat/application/calculations/tests/test_cross_period_clean_state.py`

## Description

- Add `test_alta_containing_period_stays_in_scope_as_first_obligation`: real-storage M390/2025 with `activity_start_date=2025-10-01` (first day of 4T) suppresses 1T/2T/3T but keeps 4T in scope as the first obligation.

## Outcome

- Landed in commit `0c69ec483`. Asserts 4T is NOT suppressed (`no_prior_obligation is None`), still demands its filing (`MISSING_CURRENT_FILING_RECORD`), and the suppressed set is exactly `{1T,2T,3T}`. Boundary pinned via `Period` authority.

## Notes

- Proves the ratified boundary: alta-CONTAINING period is the first obligation, only strictly-prior suppressed.
