---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:6c26e22ec64f2a5c1fecd1f619c069da0dac9cca876e7d0496545d2c9f1b8eac'
step_id: 'S363'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unconsumed flow frontend-capability and intent enums and their self-referential taxonomy tests.

## Scope

- `core flow vocabulary`
- `flow enum and engine tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/core/flows.py`
- `M` `src/cadrumo/core/tests/test_flows_enums.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/core/tests/test_flows_enums.py src/cadrumo/application/flows/tests -q` -> `pass (141 passed)`
- `verify:` `uv run --no-sync ruff check src/cadrumo/core/flows.py src/cadrumo/core/tests/test_flows_enums.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (233 unused symbols; down from 235)`
