---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:62c22995e54685ed7cb315bdef49e6217ff1becfd4c26278e3893d7cbb696c66'
step_id: 'S14'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Test dynamic signatures type hints metadata and CLI discovery

## Scope

- `src/cadrumo/application/wizard/tests/test_commands_helpers.py`

## Changes

- `M` `src/cadrumo/application/wizard/tests/test_commands_helpers.py`
- `verify:` `uv run --no-sync ruff format --check src/cadrumo/application/wizard/tests/test_commands_helpers.py; uv run --no-sync ruff check src/cadrumo/application/wizard/tests/test_commands_helpers.py; uv run --no-sync pytest -q src/cadrumo/application/wizard/tests/test_commands_helpers.py -o addopts='' -m 'unit and hex_application' -n 0` -> `pass`
