---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:64d612bb3354662bfd16f95045adc95f9faf55c7b90bb6341ef3a4d8006d5c00'
step_id: 'S306'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the type-ignore rationale-comment census, its multi-marker vocabulary, line-window scanner, corpus floor, and synthetic string probes; retain configured type-checker diagnostics and useful local explanations.

## Scope

- `type-ignore rationale gate`
- `focused inventory tests`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_type_ignore_rationale_inventory.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S306.md`
- `verify:` `uv run --no-sync pytest -q dev/tests/test_test_inventory.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The removed gate judged only nearby comment prefixes, not whether a suppression was valid or accepted by the configured type checker. The exact production detector remains red on the wider campaign findings.
