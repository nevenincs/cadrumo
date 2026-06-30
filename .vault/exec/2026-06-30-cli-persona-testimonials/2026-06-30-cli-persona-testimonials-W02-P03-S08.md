---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S08'
related:
  - "[[2026-06-30-cli-persona-testimonials-plan]]"
---

# Verify operator-visible M303 wallet guidance and translations

## Scope

- `src/aeat/locales`

## Description

- Fix Catalan and Hungarian IVA wallet seed help so zero carry-forward is not
  conflated with proof of a true first IVA period.
- Preserve the separate automatic `first_period_zero` explanation as a
  calculation and reconciliation result proven by activity-start and registry
  conditions.
- Re-review locale formatting and placeholder safety.

## Outcome

Commits `c35feaba5` and `5abb0081e` updated
`src/aeat/locales/ca.yml` and `src/aeat/locales/hu.yml`. The final wording says
`--amount 0` declares a zero opening balance and may also apply to prior filers
whose last M303 left no pending compensation. Re-review found no remaining
overclaim or locale formatting issue.

## Notes

Final focused locale/M303 verification reported 26 passed and 1 deselected.
