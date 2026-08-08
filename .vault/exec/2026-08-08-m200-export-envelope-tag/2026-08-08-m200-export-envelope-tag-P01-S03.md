---
tags:
  - '#exec'
  - '#m200-export-envelope-tag'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:591b809b4c086fd456807ab1074170d0a982edd4d90dc8ca4a10c85492849350'
step_id: 'S03'
related:
  - "[[2026-08-08-m200-export-envelope-tag-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace m200-export-envelope-tag with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-08-08-m200-export-envelope-tag-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The promote the AUX and header filler fields to literal and header kind and ## Scope

- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0001-modelo-200-page-000.toml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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

<!-- Where the evidence is that something RAN, quote the instrument rather than
     summarising it: the invocation, then the runner's verbatim summary line.

         uv run --no-sync pytest <paths> -m integration -n 0
         15 passed in 10.35s

     The invocation shows the selection (marker expression and path scope); the
     summary line shows what that selection produced. A run that selected nothing
     exits zero and reads as green, so a paraphrase such as "the tests pass"
     discards exactly the part a reader needs. Quote, do not summarise. -->

The same byte-level assertion covers this Step: its marker and EEDD assertions at
bytes 17-21, 92-95, 100-108 and 322-327 are what prove the four promotions render.

    uv run --no-sync pytest src/cadrumo/application/filing/tests/test_export.py -k "modelo_200" -n0 -q
    4 passed, 42 deselected in 18.08s

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
