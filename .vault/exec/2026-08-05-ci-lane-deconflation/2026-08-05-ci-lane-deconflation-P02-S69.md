---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:24a72b1400be21d41b9c4ed4966b3dc6fd85d96e236f68f805ff6de6b9475416'
step_id: 'S69'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# The last 5 ratchet entries cannot be closed by a runtime discriminator at all, and the reason is uniform. MEASURED 2026-08-28 across both remaining modelos, applying the obligatorio test that Modelo 296 forced into the method. M184: scanning both Tipo-2 sheets for runs one fills and the other declares filler yields seven candidates on the entidad side -- RETENCIONES E INGRESOS A CUENTA @233+12, SITUACION DEL INMUEBLE @245+1, REFERENCIA CATASTRAL @246+20, DETALLE DE GASTOS RENDIMIENTOS @266+130, CRITERIO DE COBROS Y PAGOS @396+1, a second DETALLE block @397+101, and NUMERO DE DIAS DE ARRENDAMIENTO @498+3 -- and exactly one on the socio side, NIF DEL REPRESENTANTE FISCAL @27+9. EVERY ONE is obligatorio=False or carries no marker at all, including both large DETALLE blocks. M296 measured the same way: all eight fields in its otherwise-perfect @402-499 run are optional. SO THE STRUCTURAL TEST PASSES EVERYWHERE AND THE SEMANTIC TEST FAILS EVERYWHERE. A `RecordDiscriminator` is consumed by the parser at RUNTIME to decide which record a row is, so `requires='non_blank'` asserts that a real filing always populates the span. On these runs that assertion is false by AEAT's own marking: an entidad record for a rented property with no gastos detail, or a perceptor with no prior payer and no LEI, would be mis-identified. Closing a coverage-checker tie by that means would plant a record-identification defect in a filed return. THE REMAINING FIVE THEREFORE NEED A MECHANISM THAT MAKES NO RUNTIME CLAIM, which is exactly the option this campaign set aside earlier: the generator mapping already records `record_identity` per entry, naming which design sheet each record belongs to, and the coverage checker re-derives that from constants instead of reading it. Surfacing it asserts nothing about what a filing contains -- it states which sheet the record was authored against, which is a fact about the registry rather than about a taxpayer. It is an export-schema change, since production must not import dev and the identity would have to travel in the generated fragments the checker already reads, so it is ADR-grade. That is the honest endgame for these five: not more authoring, and not a looser join, but carrying an authored fact the checker currently guesses at

## Scope

- `src/cadrumo/domain/calculations/registry/schema_exports.py`
- `_validate_export_layout_coverage.py and dev/registry/mappings`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S69.md`
- `M` `.vault/plan/2026-08-05-ci-lane-deconflation-plan.md`
- `verify:` `uv run --no-sync pytest -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py` -> `pass` (4 passed in 101.04s)

## Notes

- Current HEAD measures no unjoined design sheets: the declared ratchet inventory and the live full-registry scan are both empty. The prior five-entry `record_identity` proposal is therefore no longer needed; no ADR, schema, generated-output, mapping, or runtime change was made.
