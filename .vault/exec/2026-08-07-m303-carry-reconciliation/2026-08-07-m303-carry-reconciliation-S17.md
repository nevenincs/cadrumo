---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:650b5fd1469601036656dbd577665f5c9075113d2fb7c92ab848eef7a90f9215'
step_id: 'S17'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
  - "[[2026-08-09-m303-carry-reconciliation-did-page-s17-audit]]"
---
# S17 account-bearing DID export verification

## Scope

- `src/cadrumo/application/filing`
- `src/cadrumo/core`

## Description

- Verify public Modelo 303 exports across refund, domiciliation, ingreso, and negativa dispositions.
- Add exporter-produced D and I regression assertions alongside the existing U and N paths.
- Confirm the shared DID predicate drives both renderer suppression and parity derivation.
- Obtain an independent S17 review without widening Nota 3 behaviour.

## Outcome

The first half of S17 is complete. Public U renders the DID page from the persisted charge account only; public D retains the refund account when a distinct charge account is present; public I and N omit DID. The shared account-bearing predicate remains D/V/X/U versus C/I/N/G for renderer and parity use. Nota 3 remains deferred to S19 because its casilla 111 and page-3 cancellation inputs are not disposition facts.

## Verification

`uv run --no-sync pytest -q src/cadrumo/application/modelo/tests/test_export_output_paths.py src/cadrumo/application/modelo/tests/test_modelo_303_refund_account_missing_e2e.py src/cadrumo/application/filing/tests/test_did_page_bank_account_dispositions.py src/cadrumo/application/filing/tests/test_export_completeness_sets.py src/cadrumo/core/tests/test_result_disposition_bank_account.py`

`33 passed in 21.73s`

`uv run --no-sync ruff check src/cadrumo/application/modelo/tests/test_export_output_paths.py src/cadrumo/application/modelo/tests/test_modelo_303_refund_account_missing_e2e.py`

`All checks passed!`

The independent audit recorded no triaged findings and reran the 33-test payload/parity lane.

## Notes

The first public-D test attempt used a zero-result fixture, so a DID page was correctly absent. It was discarded in favour of the existing real engine-computed negative-credit REDEME public-export path. No production disposition or S19 Nota 3 behaviour changed.
