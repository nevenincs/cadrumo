---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:5cf7380168f218b7d8e1fc68bf41334e4789c5f837dfae82b33a3560c225a813'
step_id: 'S236'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the broken machine-secret importer filename census and fixed command-identity roster from the command-spec authority test; retain graph-derived projection checks and planted channel/contract refusal proofs.

## Scope

- `Machine-secret command-spec authority tests`
- `accepted production-authored command graph decision`
- `focused gate`
- `cadence reference`
- `and Step Record.`

## Changes

- `M` `src/cadrumo/entrypoints/cli/tests/test_machine_secret_spec_authority.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/cli/tests/test_machine_secret_spec_authority.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s236 src/cadrumo/entrypoints/cli/tests/test_machine_secret_spec_authority.py` -> `pass`
