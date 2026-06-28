---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S10'
related:
  - "[[2026-06-13-first-filer-attestation-plan]]"
---




# Emit a non-blocking advisory verification finding when a suppression rests on an operator-declared-but-uncorroborated activity-start date, mirroring the existing unstamped-revision advisory severity that keeps the grant path open

## Scope

- `src/aeat/application/modelo/_verification_actions.py`

## Description

- Emit `_cross_period_operator_declared_suppression_advisory_finding`: a non-blocking `ADVISORY` (`WARNING` severity) finding when a suppression rests on an operator-declared (uncorroborated) activity-start date, mirroring the existing unstamped-revision advisory severity that keeps the grant path open.

## Outcome

- Landed in commit `5d6549183`. The advisory names the modelo/year/period and the declared date and states it is not yet censo-corroborated. Proven by P04.S16 `test_verify_surfaces_operator_declared_suppression_advisory_without_blocking`.

## Notes

- WARNING severity keeps the grant path open per `_classify_verification_outcome`; the suppression is never presented as AEAT-authoritative.
