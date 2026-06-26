---
tags:
  - '#exec'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S10'
related:
  - "[[2026-06-21-crossperiod-filing-deadlock-plan]]"
---




# Reconcile the local cross-period carry tests to admit-with-advisory for same-year chains while keeping the cross-year prior blocking and preserving the app_filing-non-official invariant

## Scope

- `src/aeat/application/modelo/tests/test_local_cross_period_carry.py`

## Description

- Reconcile `test_local_cross_period_carry.py`: the same-year case now asserts admit-with-advisory (the non-official-local-chain advisory surfaces and verify grants), and asserts the cross-year dependency is NOT relaxed and still blocks.
- Preserve `test_app_filing_source_kind_is_not_official_evidence` verbatim (the `app_filing`-non-official data invariant).

## Outcome

Landed in commit `84add274d`. `test_local_cross_period_carry.py` 5/5 green; real-behaviour, no mocks/skips/xfail.

## Notes

