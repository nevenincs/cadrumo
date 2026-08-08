---
tags:
  - '#exec'
  - '#m200-export-envelope-tag'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:3081dfdb68ffe9d0df0d5538c1d6d57ccbd0b65df3ae4e3369d9d814c8b00f96'
step_id: 'S03'
related:
  - "[[2026-08-08-m200-export-envelope-tag-plan]]"
---

# promote the AUX and header filler fields to literal and header kind

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0001-modelo-200-page-000.toml`

## Description

- Promote the offset-18 filler to a literal `<AUX>` and the offset-323 filler to a
  literal `</AUX>`. Both are `Constante` fields on sheet `DP200000` rows 2 and 8,
  not reserved space, so a filler there emits blanks where AEAT requires markers.
- Promote the offset-93 filler to a `program_version` header field and the
  offset-101 filler to a `presenter_nif` header field, matching the sheet's rows 4
  and 6 ("Versión del programa" and "NIF Empresa Desarrollo"). Both stay
  `required = false`, because the sheet marks them for entidades desarrolladoras
  to fill.
- Leave offsets 23, 97 and 110 as fillers: those three are the rows the sheet
  really does reserve for the Administración and instructs to fill with blanks.

## Outcome

The four promoted slots render their declared content and the three genuinely
reserved slots stay blank, so the record now distinguishes AEAT's constants from
AEAT's reserved space instead of treating both as filler. The header field names
match the keys the export already supplies for the sibling modelos, so no header
plumbing changed.

## Verification

The same byte-level assertion covers this Step: its marker and EEDD assertions at
bytes 17-21, 92-95, 100-108 and 322-327 are what prove the four promotions render.

    uv run --no-sync pytest src/cadrumo/application/filing/tests/test_export.py -k "modelo_200" -n0 -q
    4 passed, 42 deselected in 18.08s

## Notes
