---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:551066cdaacd8cf3935cf4925fb63591a1559f36e4eff7cd0a86314379f23696'
step_id: 'S367'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unused fixed-width record-payload convenience renderer and its wrapper-only line-ending protocol state.

## Scope

- `fixed-width registry codec`
- `codec and outbound renderer tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/fixed_width_codec.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/fixed_width_codec.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/domain/calculations/registry/tests/test_fixed_width_codec.py src/cadrumo/adapters/outbound/aeat/export/tests/test_registry_record_renderer.py -q` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
