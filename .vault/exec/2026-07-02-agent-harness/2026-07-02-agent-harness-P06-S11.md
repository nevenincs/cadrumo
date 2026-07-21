---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S11'
related:
  - "[[2026-07-02-agent-harness-plan]]"
---

# status:done (pre-existing, commits 2c8020cf5/a375ed6ba/f87fff631) - anchor golden scenarios for modelo 130 and modelo 303 with AEAT numeric value-oracles

## Scope

- `src/aeat/agent/eval/tests/test_modelo_130_golden.py`

## Description

- Build `GoldenScenario`/`GoldenResult` models and a runner over the
  Layer-2/3 vertical slice.
- Author the modelo 130 golden scenario grounded in a real AEAT numeric
  value-oracle; add the modelo 303 counterpart.

## Outcome

Landed pre-existing at commits `2c8020cf5` (Layer 2/3 vertical slice),
`a375ed6ba` (verification-contract dimension), and `f87fff631`
(figure-level numeric value-oracle gate). These are the anchor scenarios the
seven new golden categories (`P06.S12`-`P06.S18`) extend.

## Notes

None.
