---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S20'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W03.P05.S20 backend calculate input ownership

Scope:
- `src/aeat/application/modelo/_calculate_input.py`
- `src/aeat/entrypoints/cli/_modelo_cli_support.py`

## Description

- Verified that the application layer still owns calculation input policy through `build_work_calculate_input_bundle`.
- Verified backend ownership of casilla normalization, non-numeric casilla refusal, row aggregate validation, binding versus enum-binding split, relation decimal coercion, and legal shortcut application.
- Kept the CLI support module limited to operator-token parsing and delegation into `build_work_calculate_input_bundle`.

## Outcome

The transport parsing move did not transfer calculation policy into the CLI. `_calculate_input.py` remains the policy owner for calculation inputs and shortcut semantics.

## Verification

- `uv run --no-sync ruff check src/aeat/application/modelo/_calculate_input.py` passed.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo_calculation_through_real_cli.py -q` passed with 5 tests.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo_casilla_normalisation.py src/aeat/entrypoints/cli/test_modelo_work_ux.py -k "non_numeric or casilla or calculate" -q` passed with 8 selected tests.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_work_calculate_borrador.py src/aeat/entrypoints/cli/test_modelo_source_mesh_calculate.py -q` passed with 4 tests.

## Notes

- No `_calculate_input.py` code change was required for this step; the step is closed on preservation and verification evidence.

