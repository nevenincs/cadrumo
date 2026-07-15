---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S46'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# regression test asserting build_overview_explain and build_overview_calendar produce identical ApplicabilityVerdict per modelo for the same profile

## Scope

- `pin the current correct agreement state to prevent future drift`
- `src/aeat/application/overview/test_calendar_applicability_consistency.py`

## Description

- Reconciled the calendar/applicability consistency test to the Wave-2 review.
- Confirmed `acea52801e` supplied the reviewed implementation.
- Added this per-step execution record without changing production sources.

## Outcome

The 2026-05-29 review accepted the test coverage. This record restores the one-Step, one-record traceability edge.

## Notes

The same reviewed commit also supports S43 and S44; each row receives its own record.
