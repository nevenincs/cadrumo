---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:9504b7b890748f0950f7c3f3a3576be1b9e349222bba23f2ee61968f16083a14'
step_id: 'S65'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# The remaining join-ratchet entries need a RECORD-level discriminator, not a design constant -- and Modelo 349 already declares one the coverage checker never reads. MEASURED 2026-08-28, and this CORRECTS an earlier reading of the same rows. FIRST FINDING, which stands: none of the seven sheets can be closed by authoring a DESIGN constant, because AEAT publishes none. All seven declare exactly two constants -- the tipo marker and the modelo number -- and every one is already matched by a record. Modelo 193 is the clearest: `modelo-193-perceptor` and `modelo-193-gastos` both declare {(1,1): '2', (2,3): '193'} and nothing else, while their sheets declare the same two. What separates them is SHAPE, 41 fields against 9 on the record side and 39 against 10 on the design side. SECOND FINDING, which corrects the first's conclusion: `ExportRecordDefinition` carries a `discriminator` field -- a REGISTRY concept rather than an AEAT one -- so a discriminator CAN be authored even where AEAT prints no constant. Modelo 349 already has one on both tying records: `modelo-349-operador` declares `RecordDiscriminator(offset=147, length=32, requires='blank')` and `modelo-349-rectificacion` declares the same coordinate `requires='non_blank'`. The coverage checker does not consult it -- `discriminator` appears once in that module, in a comment about an unrelated page discriminator -- so this is the same shape as the `_record_literals` gap already fixed for design constants: the declaration exists, is authored, and the checker cannot see it. THE DESIGN CORROBORATES THE DISCRIMINATOR: at that exact coordinate the Operador sheet declares a field with NO content while the Rectificaciones sheet declares one carrying 'Estos campos se cumplimentaran...'. So the two sheets really do differ there, which is what makes the record-level rule a faithful reading rather than an invention. WHAT IS STILL A DECISION, and why this is not being implemented on the spot: teaching the join to consult the discriminator means mapping a RUNTIME blankness rule onto a DESIGN content cell -- requires='blank' matching a sheet field that declares no content, requires='non_blank' matching one that does. That is an inference across two vocabularies, and today has repeatedly shown that a plausible cross-vocabulary rule is exactly where a matcher admits more than intended. It wants grounding before it ships. If it holds it closes Modelo 349's two entries with no new schema at all, and gives Modelo 184, 193 and 296 an authorable route for the remaining five

## Scope

- `src/cadrumo/domain/calculations/registry/_validate_export_layout_coverage.py and the export record discriminator declarations`

## Changes

- `verify:` `uv run --no-sync pytest -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py::test_the_unjoined_design_sheet_inventory_is_exact src/cadrumo/domain/calculations/registry/tests/test_modelo_349_registry.py::test_committed_modelo_349_record_design_round_trips_declarante_operador_rectificacion` -> `pass`

## Notes

- Reconciliation only: no source or registry declaration changed. Verified predecessor `ce7ed9c74ef` makes `_join_record` consult a discriminator only among tied literal winners; a unique literal winner returns before it, and silent/ambiguous discriminator evidence remains unjoined.
- Current M349 declarations remain `offset=147,length=32,requires=blank/non_blank`, corroborated by the design round-trip. After S119's corrected scan, M296 is the sole unresolved ratchet entry; no M184/M296 runtime discriminator or S69 mechanism was authored here.
