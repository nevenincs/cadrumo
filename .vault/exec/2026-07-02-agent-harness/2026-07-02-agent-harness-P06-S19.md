---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S19'
related:
  - "[[2026-07-02-agent-harness-plan]]"
---

# status:done (pre-existing) - determinism-replay pinning test confirming byte-identical trajectory replay excluding scenario-declared non-deterministic fields

## Scope

- `src/aeat/agent/eval/tests/test_tool_call_replay.py`

## Description

- Confirm determinism-replay pinning: filing year/period explicit, revision
  resolved via `select_revision` (law-determined, never injected),
  `work_unit_id` scenario-declared or excluded from byte-identical compare.
- Confirm faithfulness/HITL determinism by construction.

## Outcome

Pre-existing; re-verified green in this review pass alongside the seven new
golden category files.

## Notes

None.
