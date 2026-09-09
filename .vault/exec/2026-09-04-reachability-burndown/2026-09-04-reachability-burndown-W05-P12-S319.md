---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:ce100a3e77e489713bfbfb983f424bc05248c85cb03d0d721e455fe86d59c9f2'
step_id: 'S319'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete displaced projection version and digest-adapter declarations from the facade

## Scope

- `operation projection facade`
- `focused projection contracts`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `M` `src/cadrumo/application/operations/projection_services.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync python -m py_compile src/cadrumo/application/operations/projection_services.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/operations/tests/test_projection_services.py src/cadrumo/application/operations/tests/test_cancellation_cleanup.py` -> `pass`
