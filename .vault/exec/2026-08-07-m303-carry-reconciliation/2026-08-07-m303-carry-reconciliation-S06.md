---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:befc4f82851a226e818575b8e100ba15f32b939eb6752369efac7acebf36292c'
step_id: 'S06'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---
# DEFERRED - assert the disposition-blind available reconstruction in the annual partition instead of relying on a transitive upstream rewrite in another package

## Scope

- `src/cadrumo/application/calculations/_iva_compensation_annual_partition.py`
- annual partition, binding-prefill, continuity, FIFO, ordinary fold-in, and simplificado live-M390 tests

## Description

- Replace bare Modelo 303 observation input with persisted `ObservationEnvelopePayload` records in the annual partition reader.
- Revalidate the normalized disposition-aware envelope after decryption and again before constructing each FIFO period state.
- Require explicit normalized generated and available amounts; remove the disposition-blind `posterior + generated` reconstruction.
- Migrate real annual-M390 test filings to sign-compatible filing-boundary dispositions and cover legacy, conflicting, and persisted-pair-tamper refusals.

## Outcome

The annual FIFO partition accepts only validated filed carry evidence. Missing, legacy, conflicting, or pair-mismatched envelope evidence fails closed before it can influence M390 boxes 97 or 662; an identical negative C filing carries credit while D produces zero in both boxes.

## Verification

`uv run --no-sync pytest src/cadrumo/application/calculations/tests/test_m303_carry_ingress.py src/cadrumo/application/calculations/tests/test_iva_compensation_filed_observations.py src/cadrumo/application/calculations/tests/test_modelo_303_refunded_period_carry.py src/cadrumo/application/calculations/tests/test_iva_compensation_relation_prefill.py src/cadrumo/application/calculations/tests/test_binding_prefill.py src/cadrumo/application/calculations/tests/test_modelo_390_303_reconciliation_continuity.py src/cadrumo/application/live/tests/test_filed_header_facts_reach_storage.py src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py src/cadrumo/application/modelo/tests/test_filed_observation_storage_context.py src/cadrumo/application/modelo/tests/test_e2e_ledger_m303_quarters_to_m390_annual.py src/cadrumo/application/modelo/tests/test_modelo_390_fifo_carried_pending.py src/cadrumo/application/modelo/tests/test_modelo_390_303_fold_in_live.py src/cadrumo/application/modelo/tests/test_modelo_390_303_simplificado_fold_in_live.py -q`

`119 passed in 29.64s`

`uv run --no-sync pytest src/cadrumo/application/calculations/tests/test_iva_compensation_relation_prefill.py -q`

`6 passed in 14.76s`

`uv run --no-sync basedpyright src/cadrumo/application/calculations/_iva_compensation_annual_partition.py src/cadrumo/application/calculations/tests/test_iva_compensation_relation_prefill.py src/cadrumo/application/calculations/tests/test_binding_prefill.py src/cadrumo/application/calculations/tests/test_modelo_390_303_reconciliation_continuity.py src/cadrumo/application/modelo/tests/test_modelo_390_fifo_carried_pending.py src/cadrumo/application/modelo/tests/test_modelo_390_303_fold_in_live.py src/cadrumo/application/modelo/tests/test_modelo_390_303_simplificado_fold_in_live.py`

`0 errors, 0 warnings, 0 notes`

## Notes

Formal S06 review approved with no findings. S08 wallet readers were not modified.
