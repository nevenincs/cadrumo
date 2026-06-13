---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S15'
related:
  - "[[2026-06-13-first-filer-attestation-plan]]"
---




# Add an anti-tautology proof that a REAL prior filing post-dating the declared alta still produces a cross-period blocker and still demands official AEAT evidence

## Scope

- `src/aeat/application/calculations/tests/test_cross_period_clean_state.py`

## Description

- Add `test_real_prior_filing_post_dating_alta_still_blocks_anti_tautology`: real-storage M390/2025 with `activity_start_date=2025-01-01` keeps every 2025 quarter in scope; with no AEAT evidence seeded the gate blocks exactly as without any date.
- Add the non-calendar-anchor guard test proving a period with no calendar span is never silently suppressed.

## Outcome

- Landed in commit `0c69ec483`. Asserts `clean` False, zero suppressed dependencies, and the genuine missing-observation / missing-filing blockers still fire. The gate is not vacuously open.

## Notes

- Anti-tautology: an operator cannot scope away an obligation that fell on/after the claimed start; the in-scope evidence demand still surfaces.
