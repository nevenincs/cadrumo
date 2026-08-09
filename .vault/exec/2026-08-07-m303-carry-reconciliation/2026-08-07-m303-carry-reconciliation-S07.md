---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:0d70e4cbdbb5245d11ab4036f2f2ea1e324ae5702ea143baf86d36bd278e8527'
step_id: 'S07'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---
# DEFERRED - refuse a persisted compensation pair where a directly filed disponible casilla overwrites available without generated following it

## Scope

- `src/cadrumo/application/calculations/_observations_repository.py`
- `src/cadrumo/application/calculations/_m303_carry_ingress.py`
- `src/cadrumo/application/calculations/_iva_compensation_history.py`
- `src/cadrumo/application/live/_filed_observation_persistence.py`
- `src/cadrumo/application/modelo/_filed_revision_observation.py`
- focused local and official persistence, carry-ingress, and ledger workflow tests

## Description

- Prepare the validated observation envelope without writing it, then atomically persist its normalized M303 carry projection and derived IVA-history state through one secure-object batch.
- Remove raw filed-observation history constructors and their implicit non-refund derivation; make history consume only an already-normalized envelope.
- Require one sign-compatible filing disposition, reject typed/header conflicts and divergent available/generated values before either record is written, and leave legacy envelopes readable but carry-ineligible.
- Migrate direct local-M303 test callers to explicit filing-boundary dispositions while retaining the missing-disposition refusal.

## Outcome

Local and official M303 filing paths now co-emit a single disposition-aware carry/history pair or persist neither record. No remaining history path chooses a directly filed available value over the semantic normalized projection.

## Verification

`uv run --no-sync pytest src/cadrumo/application/calculations/tests/test_m303_carry_ingress.py src/cadrumo/application/calculations/tests/test_iva_compensation_filed_observations.py src/cadrumo/application/calculations/tests/test_modelo_303_refunded_period_carry.py src/cadrumo/application/live/tests/test_filed_header_facts_reach_storage.py src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py src/cadrumo/application/modelo/tests/test_filed_observation_storage_context.py src/cadrumo/application/modelo/tests/test_e2e_ledger_m303_quarters_to_m390_annual.py -q`

`96 passed in 32.00s`

`uv run --no-sync basedpyright src/cadrumo/application/calculations/_observations_repository.py src/cadrumo/application/calculations/_m303_carry_ingress.py src/cadrumo/application/calculations/_iva_compensation_history.py src/cadrumo/application/calculations/__init__.py src/cadrumo/application/calculations/_ports.py src/cadrumo/application/calculations/_errors.py src/cadrumo/application/live/_filed_observation_persistence.py src/cadrumo/application/modelo/_filed_revision_observation.py src/cadrumo/application/calculations/tests/test_m303_carry_ingress.py src/cadrumo/application/calculations/tests/test_iva_compensation_filed_observations.py src/cadrumo/application/calculations/tests/test_modelo_303_refunded_period_carry.py src/cadrumo/application/live/tests/test_filed_header_facts_reach_storage.py src/cadrumo/application/modelo/tests/test_filed_observation_storage_context.py src/cadrumo/application/modelo/tests/test_e2e_ledger_m303_quarters_to_m390_annual.py`

`0 errors, 0 warnings, 0 notes`

`uv run --no-sync pytest -m integration src/cadrumo/adapters/outbound/aeat/sede/tests/test_submitted_file_header_facts.py -q`

`19 passed in 15.74s`

`uv run --no-sync pytest -m "not external_tool and not os_keychain" src/cadrumo/domain/iva_compensation/tests/test_filed_derivation_disposition.py -q`

`10 passed in 3.11s`

## Notes

Formal S07 review approved after the direct local caller migration. S06 annual partitioning and S08 wallet consumers were not modified.
