---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S10'
related:
  - "[[2026-07-02-agent-harness-plan]]"
---

# status:done (commit 00349c998) - add the end-to-end wiring test exercising a persona's tool boundary through the live dispatch path

## Scope

- `src/aeat/entrypoints/mcp/tests/test_persona_server_wiring.py`

## Description

- Author `test_persona_server_wiring.py`, exercising a persona's
  declared `(family, mutability)` tool boundary through the live MCP
  `PreToolUse` dispatch path end to end, not the filter in isolation.
- Assert an out-of-scope tool call is refused by the real dispatch
  path, proving prose and runtime behaviour cannot diverge.

## Outcome

Landed in commit `00349c998` alongside the `P05.S09` wiring change (one
commit; the declaration and its end-to-end proof landed together). 41
MCP tests green at landing.

## Notes

None.
