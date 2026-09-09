---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:2919716b397d05e7a6ca65d797c10187b56f64a04ef799fa82ac64d856708af8'
step_id: 'S307'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the date/boolean parsing AST enrollment engine, its whole-layer exclusions, seeded binding assumptions, production path/line exemptions, detector-authored token vocabulary, and embedded-code probes; retain canonical parser behavior.

## Scope

- `parsing enrollment inventory`
- `focused parsing tests`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_parsing_enrollment_inventory.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S307.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/core/parsing/tests` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Canonical parser behavior remains covered by 35 focused tests. The removed AST gate inferred provenance through exclusions and adjudications rather than exercising those boundaries; the exact production detector remains red on the wider campaign findings.
