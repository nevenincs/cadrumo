---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S19'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W03.P05.S19 calculate transport parsing support module

Scope:
- `src/aeat/entrypoints/cli/_modelo_cli_support.py`
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/test_work_calculate_row_flag.py`

## Description

- Moved shared CLI token parsing helpers from `_modelo.py` to `_modelo_cli_support.py`.
- Centralized `parse_kv_spec`, binding override parsing, casilla override parsing, typed row parsing, optional decimal parsing, maternity-month parsing, and `work_calculate_input_bundle_from_cli`.
- Kept `_modelo.py` using imported helper aliases for discovery, projection, amendment, and calculate registrar wiring.
- Preserved the legacy `_modelo.py` `_parse_row_spec` alias for existing tests while keeping the implementation in the support module.
- Re-exported row DTOs through the application facade so production CLI support does not import private domain row modules.

## Outcome

Calculate transport parsing is centralized in `_modelo_cli_support.py`. The root modelo CLI module no longer carries the calculate input-bundle adapter or typed row parser implementation, and production CLI support consumes row DTOs through `aeat.application.modelo`.

## Verification

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_cli_support.py src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py src/aeat/entrypoints/cli/test_work_calculate_row_flag.py` passed.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_work_calculate_row_flag.py src/aeat/entrypoints/cli/test_modelo.py -k "parse_casilla_override or parse_binding_override or ParseRowSpec" -q` passed with 36 selected tests.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_work_calculate_borrador.py src/aeat/entrypoints/cli/test_modelo_source_mesh_calculate.py -q` passed with 4 tests.

## Notes

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_cli_module_size.py -q` currently fails because `_app_live.py` has 2262 lines against a frozen budget of 2117. That file is outside this modelo calculate slice and was not changed here.
