---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S22'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W03.P06.S22 row flag parsing persistence and rendering

Scope:
- `src/aeat/entrypoints/cli/test_work_calculate_row_flag.py`
- `src/aeat/entrypoints/cli/_modelo_cli_support.py`

## Description

- Updated row parser tests to import `parse_row_spec` from `_modelo_cli_support.py`, the new parser owner.
- Ran row parser and row persistence/rendering tests after the calculate helper move.
- Ran additional calculate row-adjacent tests for borrador and source mesh persistence.

## Outcome

Row flag parsing and calculate persistence behavior continue to pass after the parser relocation.

## Verification

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_work_calculate_row_flag.py src/aeat/entrypoints/cli/test_modelo.py -k "parse_casilla_override or parse_binding_override or ParseRowSpec" -q` passed with 36 selected tests.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_work_calculate_borrador.py src/aeat/entrypoints/cli/test_modelo_source_mesh_calculate.py -q` passed with 4 tests.

