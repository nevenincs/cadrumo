---
tags:
  - '#exec'
  - '#mcp-protocol-hardening'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S01'
related:
  - "[[2026-07-08-mcp-protocol-hardening-plan]]"
---

# Add the supervised subprocess runner: per-tier timeout table keyed off the command classification, cooperative cancellation, and Windows process-tree termination

## Scope

- `src/aeat/entrypoints/mcp/_call_runtime.py`

## Description

- Implemented as part of the P01 (supervised call runtime) phase; the executed action is the plan step named in the heading above.

## Outcome

- Executed and merged in commit `876b6c9799` (feat(mcp): supervised call runtime with tiered timeouts, tree-kill, progress (hardening P01)). Green in the current mcp suite (241 passed) at reconciliation time.

## Notes

- Exec record backfilled by reference on 2026-07-10 during the P04 result-thinning reconciliation: this step was executed and landed by the commit(s) above before per-step exec records were authored for phases P01-P03 / P05-P06. The backfill changed no code; it records the existing landing so the plan closes with execution evidence per the plan-closure-requires-exec-records discipline.
