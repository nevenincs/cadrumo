---
tags:
  - '#exec'
  - '#cross-period-filing-clean-state'
date: '2026-06-11'
step_id: 'S55'
related:
  - '[[2026-06-05-cross-period-filing-clean-state-plan]]'
---

# `cross-period-filing-clean-state` `W07.P17.S55` exec - calculation family shard

## Description

Run the cross-period calculation-family shard covering clean-state, censal continuity, carry-forward continuity, annual/periodic reconciliation, group aggregation, and compensation continuity.

## Outcome

The application calculation shard passed across 18 cross-period/continuity test modules.

## Verification

Command passed: `uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/calculations/tests/test_modelo_036_censal_continuity.py src/aeat/application/calculations/tests/test_modelo_130_carry_forward_continuity.py src/aeat/application/calculations/tests/test_modelo_131_carry_forward_continuity.py src/aeat/application/calculations/tests/test_modelo_151_beckham_cuota_continuity.py src/aeat/application/calculations/tests/test_modelo_180_115_reconciliation_continuity.py src/aeat/application/calculations/tests/test_modelo_190_111_reconciliation_continuity.py src/aeat/application/calculations/tests/test_modelo_193_123_reconciliation_continuity.py src/aeat/application/calculations/tests/test_modelo_200_bin_carry_forward_continuity.py src/aeat/application/calculations/tests/test_modelo_200_dotaciones_deterioro_carry_continuity.py src/aeat/application/calculations/tests/test_modelo_202_cuota_base_ejercicio_anterior_continuity.py src/aeat/application/calculations/tests/test_modelo_210_irnr_continuity.py src/aeat/application/calculations/tests/test_modelo_303_compensacion_carry_anti_regression.py src/aeat/application/calculations/tests/test_modelo_303_compensacion_carry_forward_continuity.py src/aeat/application/calculations/tests/test_modelo_322_grupo_individual_continuity.py src/aeat/application/calculations/tests/test_modelo_353_grupo_aggregation_continuity.py src/aeat/application/calculations/tests/test_modelo_390_303_reconciliation_continuity.py src/aeat/application/calculations/tests/test_modelo_840_iae_continuity.py -q` with 88 tests passing.
