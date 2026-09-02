---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:b623b769e8fa3b6a12845367a15113eed21ca6302d79323261a6377c474a4fa2'
step_id: 'S13'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Harden dynamic wizard signatures against annotation representation changes

## Scope

- `src/cadrumo/application/wizard/commands.py`

## Changes

- `M` `src/cadrumo/application/wizard/commands.py`
- `verify:` `uv run --no-sync ruff format --check src/cadrumo/application/wizard/commands.py; uv run --no-sync ruff check --ignore S101 src/cadrumo/application/wizard/commands.py; uv run --no-sync python -m py_compile src/cadrumo/application/wizard/commands.py; uv run --no-sync pytest -q src/cadrumo/application/wizard/tests/test_commands_helpers.py -o addopts='' -m 'unit and hex_application' -n 0` -> `pass`
