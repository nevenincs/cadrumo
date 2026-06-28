---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S18'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W03.P05.S18 legacy calculate body registrar mount

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

- Verified that `_modelo.py` no longer contains the legacy `work_calculate` Typer command body.
- Verified that `_modelo.py` mounts calculate through `register_work_calculate_commands(...)` and supplies only boundary dependencies.
- Removed remaining local calculate input parsing helpers during `S19`, leaving `_modelo.py` as a registrar caller for calculate.

## Outcome

The root modelo CLI module now mounts calculate through the focused registrar. The monolith no longer owns calculate command body logic.

## Verification

- `rg` over `_modelo.py`, `_modelo_work_calculate_cli.py`, `_modelo_cli_support.py`, and `_calculate_input.py` confirmed the calculate command body is in `_modelo_work_calculate_cli.py`.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo_calculation_through_real_cli.py -q` passed with 5 tests.

