---
tags:
  - '#exec'
  - '#obligation-coverage-completeness'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:67082729ac85dbc60e16305beb5da0f1b37c18994c6e21911f2b6c1cb9c865ca'
step_id: 'S15'
related:
  - "[[2026-06-30-obligation-coverage-completeness-plan]]"
---

# Wire coverage onto the undeclared-profile path so it reconciles the full universe instead of returning empty.

## Scope

- `src/aeat/application/overview/_calendar.py`

## Description

- Compute `build_obligation_coverage` in the undeclared-taxpayer-model early return
  of the calendar builder (with an empty surfaced set) and attach it to the returned
  `OverviewCalendar`.

## Outcome

An undeclared profile now reports the whole obligation universe as advised /
out-of-scope (49 advised + 4 out-of-scope = 53) rather than an empty coverage report,
so the surface that can under-scope the most never reads as "nothing to file". This
is the second `overview` surface wired this pass (with `--all-profiles`); `status` and
`explain` remain tracked under the follow-up ratchet step.

## Notes
