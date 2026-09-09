---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:c4771b7f3daba08be8613456a4f00b39d74b7b66c7f4b80bda2e78b5087b1fab'
step_id: 'S368'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove the unwired Modelo 193 expense-binding export resolver and its private accumulator while retaining live observation and selector validation.

## Scope

- `Modelo 193 gasto registry bindings`
- `registry and application assembly tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/gasto193_bindings.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/gasto193_bindings.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/application/calculations/tests/test_row_set_assembly.py -q` -> `pass`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/domain/calculations/registry/tests/test_modelo_193_registry.py -q` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
