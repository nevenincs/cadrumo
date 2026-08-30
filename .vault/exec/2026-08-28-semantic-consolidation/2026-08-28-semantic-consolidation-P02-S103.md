---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:53b8a0939011de6188af383cc6862cac86be5f3dd4dbd2a20713e1596f4eb80e'
step_id: 'S103'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Derive the binding and casilla length bounds quoted in CLI refusals from the types that enforce them, replacing literals that were only ever printed and so could drift undetected

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_cli_support.py`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_modelo_cli_support.py`
- `A` `src/cadrumo/entrypoints/cli/tests/test_refusal_bounds_match_the_validator.py`
- `verify:` `pytest src/cadrumo/entrypoints/cli/tests/test_refusal_bounds_match_the_validator.py -n 0 -m ""` -> `pass`

## Notes

The bounds were only ever printed in refusal text, never enforced, so a drift
from the type would have told operators the wrong limit with nothing failing.
The new test probes the validator rather than restating the number: one
character over the quoted bound must refuse, exactly at it must not. Proved by
replacing the derivation with a wrong literal (127) and confirming it reds.
