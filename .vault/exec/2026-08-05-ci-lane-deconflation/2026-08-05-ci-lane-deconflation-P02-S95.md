---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:ce4116e6a8d8aad209c2c188737f80741d747482a71fe7ab90d26b4663fd3a12'
step_id: 'S95'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Complete the accepted-set verification and fix a red registry gate found by it, which turned out to be the same positional-selection defect corrected in the calculation-route tests earlier today. ALL THREE MODULES NOW GREEN: 41 passed sequentially over test_m390_temporal_epochs, test_filing_schedule_selection and test_binding_readiness, confirming the required accepted-set parameter on NoRevisionForPeriodError and the newly-logged branch in _binding_readiness.py broke nothing. THE GATE THAT WAS RED WAS WRONG, AND FOR A REASON WORTH NAMING. test_validator_rejects_filing_schedule_cadence_contradictions[184-annual-quarterly] died on a bare StopIteration, which reads like missing registry data. It is not: modelo 184 declares SIX revisions -- 2015, 2016-2018, 2019-2021, 2022, 2023-2024 and 2025-y-siguientes -- and only the newest two carry a filing_schedules fragment at all. The test did next(iter(modelo.revisions.values())) and then searched THAT revision for a schedule of the declared kind, so it reached 2015, found nothing, and raised. The registry is correct; older revisions predating the filing-schedule concept legitimately declare none. The test was selecting its subject BY POSITION rather than by the property it exists to exercise, so it was hostage to mapping order and to whichever revisions happen to exist. Fixed by selecting the revision and schedule together by the property under test -- the first pair whose period_kind matches -- which makes the test independent of how many revisions modelo 184 declares or in what order they arrive. Its actual subject, that the validator rejects a cadence contradiction, is unchanged and still exercised. THIS IS THE THIRD INSTANCE TODAY of one defect class: a test pinning its subject positionally rather than by identity. The calculation-route tests used OWNERSHIP[-1] and OWNERSHIP[:-1] and silently tested the wrong row once a sibling appeared; the cross-period fixture took the first filing record by work_unit_id and would have picked a superseded one; this took the first revision and found an empty search. All three read as data problems and were selection problems. Worth carrying as a review heuristic rather than three separate fixes: when a test says 'the first', ask what happens when a second arrives -- because in this repository a second always does

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_filing_schedule_selection.py`
- `src/cadrumo/domain/calculations/registry/errors.py`
- `src/cadrumo/domain/calculations/registry/temporal.py`
- `src/cadrumo/application/modelo/_binding_readiness.py`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S95.md`
- `verify:` `pytest -q -n0 src/cadrumo/domain/calculations/registry/tests/test_m390_temporal_epochs.py src/cadrumo/domain/calculations/registry/tests/test_filing_schedule_selection.py src/cadrumo/application/modelo/tests/test_binding_readiness.py` -> `41 passed in 91.52s`

## Notes

Immutable provenance for the original cadence gate is `6cb2af96c9`; immutable provenance for the property-based correction and accepted-set/readiness state is `be1ad83404`. Neither supplies recoverable historical literal pytest output. This record attests only the fresh literal receipt above; it does not claim that the historical run produced it.
