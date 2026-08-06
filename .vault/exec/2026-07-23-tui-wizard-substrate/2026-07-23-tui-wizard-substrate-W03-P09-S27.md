---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:f4f026a86d7ea290d961e5937341dd21bc332fe9264a408120f0d26cf61f9ee1'
step_id: 'S27'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Land the parity regression proving the scripted, line-mode, and full-screen paths produce identical answers and validation verdicts for a shared definition

## Scope

- `src/cadrumo/application/flows/tests/test_frontend_parity.py`

## Description

- Drive one shared `FlowDefinition` (text, integer, gated SELECT, CONFIRM, and a
  dependent page revealed by the SELECT choice) through all three real
  frontends: the scripted driver over a canonical token queue, the line
  frontend over real `prompt_toolkit` pipe keystrokes into an in-memory
  output, and the full-screen `FlowTuiApp` under Textual's headless `Pilot`.
- Assert the three frontends converge on the identical final answer map and
  the identical review-projection verdict (`submit_eligible`,
  `answered_count`, `required_remaining`).
- Assert the three frontends report the same invalid-token verdict key for a
  malformed integer, deriving the expected key from one real engine call
  rather than hardcoding it, and confirm the line frontend's captured output
  contains the `tr()`-rendered form of that same key (never a hardcoded
  prose string).

## Outcome

Landed as `5ea26c7b0d` ("test(flows): pin scripted, line, and full-screen
frontend parity"). No frontend is mocked and no engine transition is
stubbed. Re-confirmed passing at this record's time: `2 passed in 9.42s`.
This closes the plan's Wave `W03` verification criterion that scripted,
line-mode, and full-screen paths yield identical answers and validation
verdicts for a shared definition.

## Notes

The work landed on `2026-07-24T08:53:34+02:00` but the step was left
unchecked with no exec record until the `2026-07-24` fresh-context close
honesty review surfaced the gap (`profile-setup-flow` close-honesty-review
audit, finding `tui-wizard-substrate-s27-real-work-uncounted`). This record
closes that bookkeeping gap; no code changed as part of closing it.
