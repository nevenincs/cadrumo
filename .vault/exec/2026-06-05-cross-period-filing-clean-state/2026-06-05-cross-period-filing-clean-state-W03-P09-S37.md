---
tags:
  - '#exec'
  - '#cross-period-filing-clean-state'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S37'
related:
  - '[[2026-06-05-cross-period-filing-clean-state-plan]]'
  - '[[2026-06-05-cross-period-filing-clean-state-adr]]'
---

# `cross-period-filing-clean-state` `W03.P09.S37` exec - expected member coverage proof

## Description

Added a typed `CrossPeriodExpectedMemberSet` input for member fan-in dependencies and extended clean-state evidence with observed, expected, missing, and unexpected member NIFs.

## Outcome

Modelo 353's real `per_grupo_member` dependency can no longer be considered provable from partial observed member rows alone. The clean-state service now blocks when no expected roster is supplied, when expected members are missing, or when unexpected member rows would pollute the fan-in.

## Notes

This closes the backend proof surface for expected member coverage. The remaining group-fan-in work is to wire workflow/profile-provided rosters and filing-record checks per member once the persisted group roster surface exists.
