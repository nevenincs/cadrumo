---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S16'
related:
  - "[[2026-07-02-agent-harness-plan]]"
---

# status:done (commit df75c1b63) - category 7 golden scenario asserting a non-zero CLI exit code is read as a verdict payload plus a continuation verb, never an abort

## Scope

- `src/aeat/agent/eval/tests/test_exit_code_verdict_golden.py`

## Description

- Author the category-7 golden scenario dispatching a CLI verb that
  returns a non-zero exit code carrying a structured verdict payload
  (per `cli-notices-are-the-only-diagnostic-channel`).
- Assert the harness reads the non-zero exit as a verdict plus a named
  continuation verb, never treating it as an unconditional abort
  signal.
- Add the anti-tautology proof dispatched against the real CLI.

## Outcome

Landed in commit `df75c1b63` alongside the other six category golden
scenarios (cat-1/3/4/5/7/8/9). 50 eval tests green at landing.

## Notes

None.
