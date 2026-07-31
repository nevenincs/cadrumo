---
tags:
  - '#exec'
  - '#mcp-protocol-hardening'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:949247b65043632f41c9fc1ae91cc1ad2dcc4f36899cd6a199ca5895289c6281'
step_id: 'S06'
related:
  - "[[2026-07-08-mcp-protocol-hardening-plan]]"
---

# Support boolean off-tokens: the schema accepts explicit false and the argv renderer emits the secondary no-flag token for default-on pairs

## Scope

- `src/aeat/entrypoints/mcp/_input_schema.py`

## Description

- Implemented as part of the P02 (input-schema fidelity) phase; the executed action is the plan step named in the heading above.

## Outcome

- Executed and merged in commit `5c591e7734` (feat(mcp): classification table, toolset activation, input-schema fidelity, boundaries, retention). Off-token / Choice rendering refined in `e6f0db15f2` (unwrap click_type=Choice so closed enum axes render). Green in the current mcp suite (241 passed) at reconciliation time.

## Notes

- Exec record backfilled by reference on 2026-07-10 during the P04 result-thinning reconciliation: this step was executed and landed by the commit(s) above before per-step exec records were authored for phases P01-P03 / P05-P06. The backfill changed no code; it records the existing landing so the plan closes with execution evidence per the plan-closure-requires-exec-records discipline.
