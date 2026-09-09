---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:1e29b84a074a85ec123303e14064fd2ac2d29128664b09cd1573f9a21f653f05'
step_id: 'S358'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only flow back-page navigation verb left after removal of its sole frontend.

## Scope

- `flow engine API and tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/application/flows/engine.py`
- `M` `src/cadrumo/application/flows/tests/test_engine.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/application/flows/tests/test_engine.py -q` -> `pass (16 passed)`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/flows/engine.py src/cadrumo/application/flows/tests/test_engine.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (263 unused symbols; down from 264)`
