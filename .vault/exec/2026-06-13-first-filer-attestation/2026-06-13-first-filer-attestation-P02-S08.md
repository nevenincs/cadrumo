---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S08'
related:
  - "[[2026-06-13-first-filer-attestation-plan]]"
---




# Thread the declared activity_start_date parameter into evaluate_cross_period_clean_state and cross_period_dependency_requirements without letting callers pass an ad hoc dependency set, preserving registry-derived guard semantics

## Scope

- `src/aeat/application/calculations/_cross_period_clean_state.py`

## Description

- Thread an optional `activity_start_date: date | None` parameter into `evaluate_cross_period_clean_state`; it partitions the registry-derived requirements, evaluates the in-scope set as before, and emits clean facet-stamped rows for the suppressed set.
- Callers pass the declared date, never an ad hoc dependency set, preserving the registry-derived guard semantics.

## Outcome

- Landed in commit `4026deb0d`. When `activity_start_date` is `None` every dependency is evaluated exactly as before. Verified by the 29 pre-existing clean-state tests staying green plus the 5 new P04 calculations-layer tests.

## Notes

- The registry-derived-graph constraint of `2026-06-05-cross-period-calculation-guards-adr` is preserved: the scoping is a filter over the derived requirements.
