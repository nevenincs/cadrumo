---
tags:
  - '#exec'
  - '#m200-export-envelope-tag'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:43ed9e5e096164ce7e40a266337c25f04ba87112aa0f2d8d8d893e29fa865ff2'
step_id: 'S02'
related:
  - "[[2026-08-08-m200-export-envelope-tag-plan]]"
---




# replace the offset-1 filing_year draft field with the six-component open-tag composite

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0001-modelo-200-page-000.toml`

## Description

- Replace the single offset-1 length-17 `filing_year` draft field with the six
  components sheet `DP200000` row 1 spells out: literal `<T` at 1, literal `200`
  at 3, literal `0` at 6 (the discriminante), draft `filing_year` at 7 length 4,
  draft `period_code` at 11 length 2, and literal `0000>` at 13 length 5.
- Follow Modelo 111's already-shipping envelope-header composition rather than
  authoring a second idiom: the byte geometry is identical apart from the one
  character M200 reads as a regime discriminante where M111 reads a page marker,
  and every field kind used is already declared and build-validated.
- Preserve each field's `legal_refs` and `source_refs` verbatim, so every
  sub-component keeps the grounding the collapsed field carried.

## Outcome

The open tag now renders as six declared fields whose widths sum to the 17 bytes
AEAT publishes, and the year field carries the year's own width rather than the
whole tag's. The discriminante ships as a literal `0` (Normal, Abreviado y PYMES
per the sheet's own note), which is the only estado de cuentas this application
can produce a draft for; the four other regimes have no domain representation and
are not closed by this Step.

## Verification


    uv run --no-sync pytest src/cadrumo/application/filing/tests/test_export.py::test_export_writes_the_modelo_200_envelope_tags_aeat_publishes -n0 -q
    1 passed in 12.91s

## Notes

