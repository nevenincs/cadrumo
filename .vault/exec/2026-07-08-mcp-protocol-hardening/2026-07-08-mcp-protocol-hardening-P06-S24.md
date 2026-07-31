---
tags:
  - '#exec'
  - '#mcp-protocol-hardening'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:890da052ba586d96053443b16be74c276d6775fe51ac964c3f55adc1be3948ea'
step_id: 'S24'
related:
  - "[[2026-07-08-mcp-protocol-hardening-plan]]"
---

# Pin the potion model revision to a commit hash and route the model download through the app-controlled cache directory

## Scope

- `src/aeat/application/corpus_search/_query_embed.py`

## Description

- Implemented as part of the P06 (retention and posture) phase; the executed action is the plan step named in the heading above.

## Outcome

- Executed and merged in commit `f10baeca48` (chore(corpus-search): pin the potion model revision to a concrete commit SHA). Green in the current mcp suite (241 passed) at reconciliation time.

## Notes

- Exec record backfilled by reference on 2026-07-10 during the P04 result-thinning reconciliation: this step was executed and landed by the commit(s) above before per-step exec records were authored for phases P01-P03 / P05-P06. The backfill changed no code; it records the existing landing so the plan closes with execution evidence per the plan-closure-requires-exec-records discipline.
