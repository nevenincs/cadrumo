---
tags:
  - '#exec'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S09'
related:
  - "[[2026-06-21-crossperiod-filing-deadlock-plan]]"
---




# Attach cross-period dependency legal grounding (LGT art 119/120, LIVA art 99 for compensacion, RGAT art 9 for activity-start) to every cross-period and iva-wallet finding

## Scope

- `src/aeat/application/modelo/_verification_actions.py`

## Description

- Add the legal-grounding constants `_CROSS_PERIOD_DEPENDENCY_LEGAL_REFS` (LGT art-119/art-120), `_IVA_COMPENSATION_CARRY_LEGAL_REF` (LIVA art-99), and `_CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS` (RGAT RD-1065-2007 art-9).
- Add `_cross_period_dependency_legal_refs(origin_ids)` that appends LIVA art-99 when an origin id names a compensacion balance.
- Attach `legal_refs` to the blocking cross-period finding, the unstamped-revision and operator-declared-suppression advisories, the missing-activity-start finding, and the two iva-wallet findings.

## Outcome

Landed in commit `84add274d`. Every cross-period finding now surfaces its legal basis (`aeat-calculation-grounding`). Refs are catalogue ids, not invented prose.

## Notes

