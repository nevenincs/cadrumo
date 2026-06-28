---
step_id: S114
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P03.S114 — test DT12 advisory next_action localization

## Outcome

Two real-behavior tests added to `src/aeat/application/modelo/test_actions.py`:

- `test_dt12_reduccion_advisory_next_action_is_localised`: asserts next_action is
  not None, not the raw locale key, references "12" (DT provision), and >20 chars.
- `test_dt12_reduccion_advisory_next_action_differs_from_hardcoded_string`: asserts
  the pre-S113 hardcoded English substring no longer appears in next_action.

Landed in commit `e5e3c630e` by a parallel agent. 51 tests pass.

## Files touched

- `src/aeat/application/modelo/test_actions.py` (in HEAD)

## Verification

pytest 51 passed. `vault plan step check S114` applied.
