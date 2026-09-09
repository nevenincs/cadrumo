---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:48e2523d7cae27afb41e88180b887cf221018827bb8269ca387d4d4ac4f087cb'
step_id: 'S340'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove the namespace-registry source census and its pinned repository vocabulary while retaining direct registry behavior tests.

## Scope

- `namespace registry tests and reachability cadence reference`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
