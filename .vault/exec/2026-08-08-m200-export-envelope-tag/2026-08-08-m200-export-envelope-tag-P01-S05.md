---
tags:
  - '#exec'
  - '#m200-export-envelope-tag'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:91f0a40f802294d01ffe492261abea6de401bd1fa8786987a283c9f454e3b749'
step_id: 'S05'
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
     The S05 and 2026-08-08-m200-export-envelope-tag-plan placeholders are machine-filled by
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
     The confirm the byte-level test goes green for both the open tag and the close tag and ## Scope

- `src/cadrumo/application/filing/tests/test_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# confirm the byte-level test goes green for both the open tag and the close tag

## Scope

- `src/cadrumo/application/filing/tests/test_export.py`

## Description

- Re-run the byte-level assertion authored before the restructuring, unchanged,
  against the restructured declaration.
- Re-run the wider Modelo 200 export selection so the neighbouring assertions on
  the same layout — the cuota diferencial slot and the grupo mercantil parent-TIN
  slot that must stay blank — are shown to survive the record's rewrite.

## Outcome

The assertion passes at both ends of the fichero: the first 17 bytes equal
`<T200020240A0000>` and the final 18 equal `</T200020240A0000>`, the two AUX
markers render, and the two EEDD header slots carry the values the export headers
supply. The same test that reported the defect now reports the fix, so nothing
about the expectation was adjusted to fit the output.

The three sibling Modelo 200 export assertions stay green, which matters because
the restructured record sits at the head of the file and every later record's byte
position is measured from it.

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
