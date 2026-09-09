---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:ea178feb9e22f3a71e2bf1ec85687693caaa7a4560f384ccfee0a421d1e69f16'
step_id: 'S369'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete both unwired Modelo 296 export resolvers, their private row-builder vocabulary, and the builder-only test module.

## Scope

- `Modelo 296 withholding registry bindings`
- `application row assembly tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/withholding296_bindings.py`
- `D` `src/cadrumo/domain/calculations/registry/tests/test_withholding296_row_builders.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/withholding296_bindings.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/application/calculations/tests/test_row_set_assembly.py -q` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
