---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:c18b86f08bfb205c926099598f4a775a2486bc8a3c970ac4cb2cb25089246033'
step_id: 'S68'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Modelo 296's join tie cannot take a discriminator on the obvious run, because AEAT marks every field in it OPTIONAL. MEASURED 2026-08-28, and the refusal is the finding. M296's 'Tipo 2 - Registro De Perceptor' sheet ties FOUR ways rather than two -- m296-perceptor, m296-perceptor-intereses, m296-anexo-a-pagos and m296-anexo-b-certificados all agree on the only two constants the sheet declares, {(1,1): '2', (2,3): '296'}. Its sibling sheet 'Perceptor, Toma El Valor' already joins uniquely because it declares a third constant (500,1)='F', which is why only one entry is open. A STRUCTURALLY PERFECT CANDIDATE EXISTS: scanning for spans the perceptor sheet describes as real data and EVERY rival sheet describes as filler yields a contiguous run from @402 to @499 -- NIF DEL PAGADOR ANTERIOR, PROCEDIMIENTO ESPECIAL DE RETENCIONES, CLAVE DE MERCADO, CODIGO LEI DEL PERCEPTOR, NIF EN EL PAIS DE RESIDENCIA FISCAL, FECHA DE NACIMIENTO, LUGAR DE NACIMIENTO and PAIS O TERRITORIO DE RESIDENCIA FISCAL, with every rival sheet declaring the same span as filler. On the join alone that would resolve the tie. IT MUST NOT BE AUTHORED, and the reason is not about the join at all. `RecordDiscriminator` is consumed by the PARSER at runtime to identify which record a row is, so a `requires='non_blank'` rule is a claim that a real filing always populates that span. Reading the design's own obligatorio markers: every one of those eight fields is obligatorio=False, and LUGAR DE NACIMIENTO carries no marker at all. So a legitimate perceptor record that leaves all eight optional fields blank -- a resident-country NIF absent, no LEI, no prior payer -- would be MIS-IDENTIFIED by that discriminator. Authoring it would trade a coverage-checker tie for a record-identification defect on a filed IRNR return, which is a strictly worse bargain. WHAT WOULD WORK instead, unmeasured so far: discriminating the RIVALS rather than the subject, if each anexo and the intereses record has a span it always populates; or a mandatory field elsewhere in the perceptor record. Both need the same obligatorio grounding this row applied, and M296's export tree is GENERATED, so any discriminator goes in `dev/registry/mappings/modelo_296` and republishes through the generator authority rather than being hand-edited into src

## Scope

- `dev/registry/mappings/modelo_296 and the M296 export records`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/tests/test_export_parse.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S68.md`
- `M` `.vault/plan/2026-08-05-ci-lane-deconflation-plan.md`
- `verify:` `uv run --no-sync pytest -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_export_parse.py::test_m296_primary_perceptor_record_discriminator_selects_only_blank_position_500 src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py` -> `pass` (5 passed in 125.38s)
- `verify:` `uv run --no-sync ruff check dev/registry/pipeline/_semantic_map.py dev/registry/pipeline/_export_tree.py dev/registry/pipeline/_provenance_manifest.py dev/registry/mappings/modelo_296/2024/0001-records.toml dev/registry/tests/test_semantic_map_loader.py dev/registry/tests/test_export_tree.py src/cadrumo/domain/calculations/registry/tests/test_export_parse.py src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py` -> `pass`

## Notes

- Verified predecessor `ef94186c89` landed the strict semantic-map transport, canonical M296 `blank @500` declaration, and its focused generator tests while this shared worktree advanced; it was inspected, retained, and not restaged or attributed to this execution record.
- Verified predecessor `f2ac6af8f6` landed the canonical publisher's M296 generated record/provenance output carrying the same discriminator; it was inspected, retained, and not restaged or attributed to this execution record.
