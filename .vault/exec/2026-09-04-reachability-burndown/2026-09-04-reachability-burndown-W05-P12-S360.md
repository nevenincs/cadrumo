---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:714c862bded5d85f7c4ee4edb8be5d854e65d8717b06ab1bef605e378c34a3d6'
step_id: 'S360'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove twelve unused command-spec validation and recovery aliases left by the direct-import consolidation.

## Scope

- `CLI command-spec alias surface`
- `command kernel tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/entrypoints/cli/command_spec.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/entrypoints/cli/tests/test_command_spec_kernel.py -q` -> `pass (14 passed)`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/cli/command_spec.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (250 unused symbols; down from 262)`
