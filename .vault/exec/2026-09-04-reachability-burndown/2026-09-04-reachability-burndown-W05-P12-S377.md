---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:d02906e07c6c1c78287c121c4907280045ed50bc512432d0891f3e5e7abc6ef6'
step_id: 'S377'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---
# Resolve the remaining exact unreachable symbols in registry and domain ownership without duplicate authority.

## Scope

- `src/cadrumo/domain`

## Changes

- `D` `src/cadrumo/domain/calculations/registry/_withholding_193_fields.py`
- `D` `src/cadrumo/domain/calculations/registry/_withholding_rows.py`
- `D` `src/cadrumo/domain/calculations/registry/tests/test_withholding_observations.py`
- `M` `src/cadrumo/domain/calculations/registry/censo_modelos.py`
- `M` `src/cadrumo/domain/calculations/registry/external_grounding.py`
- `M` `src/cadrumo/domain/calculations/registry/live_parity.py`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact --full` -> `pass`
