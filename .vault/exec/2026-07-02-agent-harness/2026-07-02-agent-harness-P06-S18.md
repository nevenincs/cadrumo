---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S18'
related:
  - "[[2026-07-02-agent-harness-plan]]"
---

# status:done (commit df75c1b63) - category 9 golden scenario wiring faithfulness_check against a real captured calculate JSON, advisory off-handoff and hard-block at export, grounded against the M130 oracle figure to avoid false positives

## Scope

- `src/aeat/agent/eval/tests/test_faithfulness_golden.py`

## Description

- Author the category-9 golden scenario wiring `faithfulness_check`
  against a real captured `calculate` JSON payload.
- Assert an advisory fires off-handoff and a hard block fires at
  export on a hallucinated numeric, grounded against the M130 oracle
  figure so the check does not false-positive on a genuine value.
- Add the anti-tautology proof dispatched against the real CLI.

## Outcome

Landed in commit `df75c1b63` alongside the other six category golden
scenarios (cat-1/3/4/5/7/8/9). 50 eval tests green at landing.

## Notes

None.
