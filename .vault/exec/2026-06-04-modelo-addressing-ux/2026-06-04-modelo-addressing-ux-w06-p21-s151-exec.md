---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S151'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P21.S151 Focused application and CLI regression gate

Scope:
- `src/aeat/application/modelo/test_m036_lifecycle_service.py`
- `src/aeat/application/modelo/test_m036_lifecycle_contracts.py`
- `src/aeat/application/modelo/test_taxation_comparison.py`
- `src/aeat/application/modelo/test_export.py`
- `src/aeat/application/calculations/test_iva_compensation_history.py`
- `src/aeat/entrypoints/cli/test_m036_command_shape.py`
- `src/aeat/entrypoints/cli/test_iva_wallet_inspector.py`
- `src/aeat/entrypoints/cli/test_modelo_projection.py`
- `src/aeat/entrypoints/cli/test_modelo_compare.py`
- `src/aeat/entrypoints/cli/test_modelo_export_verb.py`
- `src/aeat/entrypoints/cli/test_modelo_reconcile_verb.py`
- `src/aeat/entrypoints/cli/test_modelo_work_natural_key.py`
- `src/aeat/entrypoints/cli/test_modelo_calculation_through_real_cli.py`
- `src/aeat/entrypoints/cli/test_work_calculate_row_flag.py`
- `src/aeat/entrypoints/cli/test_modelo_work_preview_maritime_exemption.py`

## Description

- Run focused application tests for M036 lifecycle, taxation comparison, export, and IVA compensation history.
- Run focused CLI tests for M036, IVA wallet, projection, compare, export, reconcile, natural-key work, calculate, row flags, and maritime preview.

## Outcome

- Application service regression lane passed: 66 tests.
- CLI regression lane passed: 100 tests.
- Row-flag tests now assert aggregate row validators at the domain boundary and preserve the real CLI persistence/rendering regression.

## Notes

- Warnings are limited to existing Click `protected_args` deprecations.

Verification:
- `uv run --no-sync pytest src/aeat/application/modelo/test_m036_lifecycle_service.py src/aeat/application/modelo/test_m036_lifecycle_contracts.py src/aeat/application/modelo/test_taxation_comparison.py src/aeat/application/modelo/test_export.py src/aeat/application/calculations/test_iva_compensation_history.py -q` - 66 passed.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_m036_command_shape.py src/aeat/entrypoints/cli/test_iva_wallet_inspector.py src/aeat/entrypoints/cli/test_modelo_projection.py src/aeat/entrypoints/cli/test_modelo_compare.py src/aeat/entrypoints/cli/test_modelo_export_verb.py src/aeat/entrypoints/cli/test_modelo_reconcile_verb.py src/aeat/entrypoints/cli/test_modelo_work_natural_key.py src/aeat/entrypoints/cli/test_modelo_calculation_through_real_cli.py src/aeat/entrypoints/cli/test_work_calculate_row_flag.py src/aeat/entrypoints/cli/test_modelo_work_preview_maritime_exemption.py -q` - 100 passed.
