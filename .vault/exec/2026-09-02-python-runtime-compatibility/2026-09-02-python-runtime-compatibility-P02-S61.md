---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:6f716d939e66df3ef049f798af14059e028b0e84fffbd629e3963595ad8a0bf7'
step_id: 'S61'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---
# Prove standard-library TOML parsing preserves the public error contract

## Scope

- `src/cadrumo/core/tests/test_toml.py`

## Changes

- `M` `src/cadrumo/core/tests/test_toml.py`
- `verify:` `uv run --no-sync ruff format --check src/cadrumo/core/tests/test_toml.py; uv run --no-sync ruff check src/cadrumo/core/tests/test_toml.py; uv run --no-sync python -m py_compile src/cadrumo/core/tests/test_toml.py; uv run --no-sync pytest -q src/cadrumo/core/tests/test_toml.py src/cadrumo/core/tests/test_toml_registry_parity.py -o addopts='' -m 'unit and hex_core' -n 0` -> `pass`
