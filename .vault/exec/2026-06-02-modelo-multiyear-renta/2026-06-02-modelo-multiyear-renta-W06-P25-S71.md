---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S71'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# write the M721 >=2-renta threshold-continuity E2E test across 2023 and 2024 via real repository/advisory evidence

## Scope

- `src/aeat/application/calculations/tests/test_modelo_721_cripto_extranjero_fidelity.py`

## Description

- Exercise Modelo 721 across the 2023 and 2024 annual contexts with the real observation repository.
- Prove custodian/token values survive the encrypted-SQL roundtrip for both years.
- Assert the re-declaration advisory fires when a grown BTC token is absent from the current declaration.
- Record both years through the non-calculation `EnrollmentRecorder` path and verify the authorization manifest.

## Outcome

- Satisfied by the current Modelo 721 crypto extranjero fidelity test.
- The test is threshold-continuity evidence, not a calculation-engine oracle.

## Notes

- The test uses repository/advisory evidence and does not prove a registry `previous_filing` row-set binding.
- The missing binding mechanism remains tracked by `S89`.
