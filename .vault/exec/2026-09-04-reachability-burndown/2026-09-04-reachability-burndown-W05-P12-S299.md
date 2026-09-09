---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:d50aed2b5b8f1af8ff14df1b74af5d0a869d98090a85cc2df298defa5f10e317'
step_id: 'S299'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the static test-rooted symbol-use graph, its dynamic-dispatch exemption ledger, copied reachability engine, and self-tests; retain executed coverage and the canonical production reachability audit as the owning signals.

## Scope

- `test-exercise static proxy`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_every_module_has_test_coverage.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S299.md`
- `verify:` `rg -n "test_every_module_has_test_coverage|_DYNAMIC_DISPATCH_EXEMPTIONS|test_every_production_module_is_exercised_by_a_test" pyproject.toml justfile dev .github src -g "!dev/.logs/**"` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The exact detector remains red on the campaign's production findings; this test-only deletion does not classify, exempt, or suppress them.
