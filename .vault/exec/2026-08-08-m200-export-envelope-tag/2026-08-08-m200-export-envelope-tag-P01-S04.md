---
tags:
  - '#exec'
  - '#m200-export-envelope-tag'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:112655a9d9da6a77133b88ebc58bc025d556ddf60c49fca9445e8802e739be25'
step_id: 'S04'
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
     The S04 and 2026-08-08-m200-export-envelope-tag-plan placeholders are machine-filled by
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
     The add the envelope-footer export fragment reusing the existing computed closing-tag key and ## Scope

- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0078-modelo-200-envelope-footer.toml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add the envelope-footer export fragment reusing the existing computed closing-tag key

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0078-modelo-200-envelope-footer.toml`

## Description

- Add one export fragment declaring record `modelo-200-envelope-footer`,
  `record_type = "envelope_footer"`, `order = 77` (immediately after the DID
  record's `order = 76`), carrying a single field at offset 1 length 18 with
  `kind = "computed"` and `computed_key = "envelope_closing_tag"`.
- Reuse the existing computed key rather than authoring a Modelo 200 variant. The
  template already renders `</T` + modelo + a hardcoded discriminante `0` + year +
  period token + `0000>`, which is byte-identical to the example content sheet
  `DP200000` row 13 prints. No application code changed.

## Outcome

The layout now declares a closing-tag record where it previously declared none,
and because records render in `order` and the footer carries no binding fields or
suppression predicate, it lands last on every Modelo 200 export.

The discriminante is rendered twice in the file now — once by the open tag's
literal and once by this computed template's hardcoded default. Both are `0` and
both are correct for every filer this application can serve, but they are one
value with two authorities, so a future regime-modelling change must move them
together.

## Verification

<!-- Where the evidence is that something RAN, quote the instrument rather than
     summarising it: the invocation, then the runner's verbatim summary line.

         uv run --no-sync pytest <paths> -m integration -n 0
         15 passed in 10.35s

     The invocation shows the selection (marker expression and path scope); the
     summary line shows what that selection produced. A run that selected nothing
     exits zero and reads as green, so a paraphrase such as "the tests pass"
     discards exactly the part a reader needs. Quote, do not summarise. -->

    uv run --no-sync pytest src/cadrumo/application/filing/tests/test_export.py -k "modelo_200" -n0 -q
    4 passed, 42 deselected in 18.08s

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
