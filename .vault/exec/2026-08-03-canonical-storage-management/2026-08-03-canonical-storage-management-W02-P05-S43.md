---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:5e13ebc40bc29ba58177c79948960ecead1727fbe88eec3a57b354fa520595b2'
step_id: 'S43'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add an MCP session-telemetry category member and delete the module-local telemetry directory constant, gated by a test asserting the telemetry directory resolves through the accessor under an overridden root

## Scope

- `src/cadrumo/entrypoints/mcp/_telemetry.py`

## Description

- Add an MCP session-telemetry category member and delete the module-local telemetry directory constant.

## Outcome

Landed in commit `b062897f8e` ("retire the last module-local storage locations"), the same commit as S42 (corpus-search). Commit message: the bare `"telemetry"` literal and its own `mkdir` workaround are replaced by a declared member with a field; the override resolves and the materialiser builds it. The MCP process keeps its own creation call deliberately — not a workaround, but because the directory is suppressed mid-session and the MCP executable never runs the CLI startup that builds the tree.

## Notes
