---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:042fa9a0f8402f444355e7d1a3e74f3ef54f7634825b834ccb5edf178a2fa9b6'
step_id: 'S40'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Rewrite the MCP telemetry prune to delegate the survivor decision to the shared selector while preserving its keep-newest-then-age disjunction, gated by a test asserting the disjunction not a conjunction

## Scope

- `src/cadrumo/entrypoints/mcp/_telemetry.py`

## Description

- Rewrite the MCP telemetry prune to delegate to `select_filesystem_retention_survivors`, preserving its keep-newest-then-age disjunction via `combine="union"` (the primitive's default is sequential/AND; a wrong default here would silently grow the telemetry directory past its bound with nothing to catch it).

## Outcome

Landed in commit `095bdc4ca2`.

## Notes

Same premature-checkbox / broken-HEAD history as S37; see that record.
