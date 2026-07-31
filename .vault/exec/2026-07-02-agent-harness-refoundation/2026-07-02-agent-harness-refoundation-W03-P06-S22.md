---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:9e880c9836c3dee7b23a1f1c984bc0ce989a78ee1bfa1c40f4dd2c325f3c193d'
step_id: 'S22'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Extend the faithfulness check with the serving-path advisory-plus-handoff-block integration surface

## Scope

- `src/aeat/entrypoints/mcp/_faithfulness.py`

## Description

- Extend `src/aeat/entrypoints/mcp/_faithfulness.py` with the serving-path
  integration surface. LOAD-BEARING DESIGN DECISION (coordinator): the model's
  free narration is client-side and invisible to the server, so the
  ENFORCEABLE boundary is the tool-call ARGUMENTS — every amount-shaped number
  an agent sends into a call must be grounded in a tool result the same
  session produced.
- `SessionGroundingWindow`: bounded FIFO of the session's result JSON,
  memory-only (results carry taxpayer figures; persisting them outside secure
  storage is forbidden).
- `arguments_faithfulness`: advisory on ordinary mutating calls, hard block
  at the export/record-marker handoff; an empty window with amount-shaped
  handoff arguments BLOCKS (figures from nowhere are the fabrication this
  gate exists to stop).
- `advisory_line`: the warning text the server surfaces on an advisory
  mismatch.

## Outcome

Authored by the coordinator. Probe verified at commit: grounded amounts pass
(separator-agnostic), ungrounded amounts block at handoff and advise
elsewhere, empty-window handoff blocks, ids/years do not false-positive, the
FIFO bound evicts. Ruff clean. Server wiring is S23 once `_server.py`
frees from W02.

## Notes

None.
