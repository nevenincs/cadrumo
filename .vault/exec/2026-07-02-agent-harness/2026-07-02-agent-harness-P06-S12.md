---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S12'
related:
  - "[[2026-07-02-agent-harness-plan]]"
---

# status:done (commit df75c1b63) - category 1 golden scenario asserting verify MUST NOT return verified_complete plus zero findings on positive input with a zero base

## Scope

- `src/aeat/agent/eval/tests/test_under_declaration_golden.py`

## Description

- Author the category-1 golden scenario dispatching a real `verify` call
  against a positive-input, zero-base draft.
- Assert `verified_complete` plus zero findings is refused; the scenario
  proves the under-declaration advisory (`no-silent-under-declaration`)
  fires rather than granting a silent-clean verdict.
- Add the anti-tautology proof dispatched against the real CLI, not a
  hand-computed expectation.

## Outcome

Landed in commit `df75c1b63` alongside the other six category golden
scenarios (cat-1/3/4/5/7/8/9). 50 eval tests green at landing.

## Notes

None.
