---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:4bac208c952aa6f8799d7791059a0870ee0a819407db125b79021ad791a2872a'
step_id: 'S179'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in context.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/core/observability/context.py`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S179.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p05-s179-execution-self-review-audit.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/core/observability/tests/test_context_propagation.py` -> `10 passed in 6.82s` (root-run evidence)
- `verify:` collect-only -> `10 tests collected in 0.12s` (root-run evidence)

## Notes

- This is a current in-band stale-plan reconciliation, with no source edit. `src/cadrumo/core/observability/context.py` is clean at 375 raw physical lines. Its only live callable pin is `run_context`, measured at 195 against a live limit of 205; every other callable has no live limit. No source provenance commit or refactor is claimed.
- No plan, baseline, threshold, `--write-baseline`, `--accept-growth`, default-index, or source mutation occurred.
