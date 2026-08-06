---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:85c66fba23207d7dc92f4d3ca4d79620f128dba7641f5ea03d40b178c97cd9dc'
step_id: 'S418'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---

# repair Modelo 100 target-aware readiness for no-business taxpayers and prove the real CLI landlord lifecycle

## Scope

- `src/aeat/application/modelo/ src/aeat/entrypoints/cli/_config/ src/aeat/domain/deadlines/_profiles.py src/aeat/application/user_profile/ src/aeat/**/tests/`

## Description

- Replace the universal activity-description baseline with a target-aware readiness boundary.
- Allow Modelo 100 for a declared non-business natural person while retaining activity requirements for economic and non-natural profiles.
- Make Modelo 130 and Modelo 303 report non-applicability before their activity baseline for no-business profiles.
- Converge `config profile validate` and `config profile status` on the same targetless baseline and expose `configured=true` on the ready status payload.
- Add real encrypted-storage CLI coverage for the landlord/pensioner lifecycle and the no-activity attribution-entity guard.
- Resolve the review-discovered attribution-status divergence before final re-review.

## Outcome

The no-business landlord scenario now has one coherent path: profile validation and status are ready, the calendar exposes Modelo 100 and suppresses 130 and 303, Modelo 100 readiness is profile-ready, and Modelo 100 work creation succeeds without `activities.description`. An economically active natural person and every non-natural entity retain the activity-description baseline. The attribution regression proves status remains unconfigured and Modelo 184 work creation refuses when that fact is absent.

Focused verification passed: Ruff; 49 integration tests across profile preflight, modelo-work readiness, and profile lifecycle; 15 unit readiness-gate tests; and 19 taxpayer-type CLI tests. Independent code review initially found the attribution-status edge, then approved the corrected final boundary with no remaining finding.

## Notes

The first broader integration attempt exposed an existing non-EU representative-validation ordering regression when applicability was moved ahead of all readiness checks. The final implementation limits applicability-first ordering to Modelo 130 and 303, whose pre-activity path needs it, and derives baseline facts from canonical stored values without constructing a taxpayer projection prematurely. The final adjacent integration run passed.
