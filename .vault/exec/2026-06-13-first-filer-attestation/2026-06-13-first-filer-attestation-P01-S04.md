---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S04'
related:
  - "[[2026-06-13-first-filer-attestation-plan]]"
---




# Add the pure period-strictly-before-activity-start predicate over a declared date routed through Period boundary authority, unit-testing that the alta-containing period is NOT before-start

## Scope

- `src/aeat/application/calculations/_cross_period_clean_state.py`

## Description

- Add the pure `_period_strictly_before_activity_start(period, activity_start_date)` predicate routed through `Period` boundary authority (`Period.end_date`, `Period.has_date_span`).
- Mirror the deadline engine pre-start gate: a period is strictly-prior only when its entire inclusive span ends before the activity-start date, so the alta-containing period stays in scope.

## Outcome

- Landed in commit `4026deb0d`. Boundary semantics verified directly: 1T ends 2025-03-31 and is strictly before a 2025-07-01 alta (True); the alta-containing 3T returns False; a non-calendar clave returns False. Proven by P04.S13 and the P04 non-calendar test.

## Notes

- Routed through the single `Period` boundary authority per `period-filter-single-boundary-authority`; no parallel inclusion math.
