---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:d8ec7a138112263cebd1f7b0e7e855df95ca898fe66c91e53312a9ecaec2f423'
step_id: 'S359'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unused fichero-BOE encoding-choice constant rather than retaining an unimplemented wire-vocabulary claim.

## Scope

- `core external constants`
- `external-constant owner tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/core/external_constants.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/core/tests/test_external_constants.py -q` -> `pass (23 passed)`
- `verify:` `uv run --no-sync ruff check src/cadrumo/core/external_constants.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact --full` -> `pass (262 unused symbols; down from 263)`
