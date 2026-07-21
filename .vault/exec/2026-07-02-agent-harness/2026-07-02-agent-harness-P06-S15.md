---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S15'
related:
  - "[[2026-07-02-agent-harness-plan]]"
---

# status:done (commit df75c1b63) - category 5 golden scenario requiring an active-profile confirmation before the first mutating verb of a sequence

## Scope

- `src/aeat/agent/eval/tests/test_active_profile_confirmation_golden.py`

## Description

- Author the category-5 golden scenario constructing a multi-step
  mutating sequence with no prior active-profile confirmation.
- Assert the harness requires an explicit active-profile confirmation
  before the first mutating verb, never proceeding on an implicit or
  stale profile selection.
- Add the anti-tautology proof dispatched against the real CLI.

## Outcome

Landed in commit `df75c1b63` alongside the other six category golden
scenarios (cat-1/3/4/5/7/8/9). 50 eval tests green at landing.

## Notes

None.
