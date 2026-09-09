---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:4f51f5d7b88fad65d67857ddb9c99a90e9eb26f194c993bc7d5e23a2ca580b5d'
step_id: 'S232'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only BORRADOR_100_SNAPSHOT_NAMESPACE string alias and export from the live Modelo 100 snapshot service; make the retained secure-storage boundary tests read the canonical LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE definition directly while preserving encrypted namespace, schema-version, and lifecycle behavior.

## Scope

- `Borrador 100 live snapshot service and focused storage tests`
- `accepted live snapshot persistence authority`
- `exact symbol signal`
- `focused gates`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `src/cadrumo/application/live/borrador_100.py`
- `M` `src/cadrumo/application/live/tests/test_borrador_100.py`
- `M` `src/cadrumo/application/live/tests/test_borrador_100_roundtrip.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/live/borrador_100.py src/cadrumo/application/live/tests/test_borrador_100.py src/cadrumo/application/live/tests/test_borrador_100_roundtrip.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s232 src/cadrumo/application/live/tests/test_borrador_100.py src/cadrumo/application/live/tests/test_borrador_100_roundtrip.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`
