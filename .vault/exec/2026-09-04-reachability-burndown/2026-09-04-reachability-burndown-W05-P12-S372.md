---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:7e46d99eb3d529c99d69b8f1734f13fc27d02cbad7f570880877a12c2a1ca471'
step_id: 'S372'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unused submission draft-loader Protocol and package prose that defended it as an exported but unconsumed adapter contract.

## Scope

- `submission protocols and package contract`
- `submission behavior tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/domain/submission/protocols.py`
- `M` `src/cadrumo/domain/submission/__init__.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/submission/protocols.py src/cadrumo/domain/submission/__init__.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/domain/submission/tests -q` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
