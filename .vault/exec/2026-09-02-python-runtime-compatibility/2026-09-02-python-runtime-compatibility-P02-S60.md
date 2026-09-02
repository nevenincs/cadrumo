---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:bbfd1a25895978b8954dd0aab22700423195f2244752ac0dca5342b6bdafa6ba'
step_id: 'S60'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---
# Replace production TOML reading with the Python standard library

## Scope

- `src/cadrumo/core/toml.py`

## Changes

- `M` `src/cadrumo/core/toml.py`
- `verify:` `uv run --no-sync ruff format --check src/cadrumo/core/toml.py; uv run --no-sync ruff check src/cadrumo/core/toml.py; uv run --no-sync python -m py_compile src/cadrumo/core/toml.py; uv run --no-sync pytest -q src/cadrumo/core/tests/test_toml.py src/cadrumo/core/tests/test_toml_registry_parity.py -o addopts='' -m 'unit and hex_core' -n 0` -> `pass`
- `verify:` `uv run --no-sync python -` (stdlib parser read of all 19,511 committed registry TOML files) -> `pass`
