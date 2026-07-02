---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S17'
related:
  - "[[2026-07-02-agent-harness-plan]]"
---

# status:done (commit df75c1b63) - category 8 golden scenario wiring confirmation_for_tool into a run so a CONFIRM-tier step is not auto-approved even with an auto-yes flag

## Scope

- `src/aeat/agent/eval/tests/test_confirmation_gate_golden.py`

## Description

- Author the category-8 golden scenario wiring `confirmation_for_tool`
  into a run so a CONFIRM-tier step is exercised end to end.
- Assert the CONFIRM-tier step is never auto-approved, even when the
  run carries an auto-yes flag, preserving the human-in-the-loop gate.
- Add the anti-tautology proof dispatched against the real CLI.

## Outcome

Landed in commit `df75c1b63` alongside the other six category golden
scenarios (cat-1/3/4/5/7/8/9). 50 eval tests green at landing.

## Notes

None.
