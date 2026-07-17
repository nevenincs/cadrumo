---
tags:
  - '#exec'
  - '#arch-remediation-source-kind-deferrals'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S09'
related:
  - "[[2026-07-02-arch-remediation-source-kind-deferrals-plan]]"
---

# Add a fired-trigger check surfaced at the swarm-audit cadence that flags a deferred kind whose trigger has fired but which remains deferred

## Scope

- `src/aeat/application/aggregation/tests/test_source_kind_enrollment_status.py`

## Description

- Add the fired-trigger check (+ an anti-tautology guard that every declared `promotion_depends_on` is a real deferred kind): a deferred kind whose named dependency has been promoted out of the deferred set, yet remains deferred, fails as a governance finding.

## Outcome

A fired promotion trigger is now mechanically detectable at the swarm-audit cadence — 'we forgot to promote it' is a test failure, not archaeology.

## Notes
