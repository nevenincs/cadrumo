---
tags:
  - '#exec'
  - '#m200-export-envelope-tag'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:7e588b2c60cfe20bc62bb6c861f7cd3a8cf007a8b49792f820293c40be4ade8a'
step_id: 'S01'
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
     The S01 and 2026-08-08-m200-export-envelope-tag-plan placeholders are machine-filled by
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
     The write a byte-level test asserting the M200 open-tag composite against current output, confirmed red and ## Scope

- `src/cadrumo/application/filing/tests/test_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# write a byte-level test asserting the M200 open-tag composite against current output, confirmed red

## Scope

- `src/cadrumo/application/filing/tests/test_export.py`

## Description

- Author one byte-level assertion over the rendered Modelo 200 fichero, covering
  both envelope ends and the markers between them: bytes 0-16 (the 17-character
  open tag), 17-21 (`<AUX>`), 322-327 (`</AUX>`), the two EEDD header slots at
  92-95 and 100-108, and the final 18 bytes (the close tag).
- Ground every expected string on sheet `DP200000` of the bundled 2024 diseño de
  registro rather than on the registry declaration under test. That sheet prints
  its row-1 and row-13 example content literally, and the existing export fixture
  files the same ejercicio and periodo the example uses, so the expected bytes are
  AEAT's own printed strings.
- Run the assertion against the unmodified declaration and confirm the red.

## Outcome

The assertion reds on the defect itself, at the first byte of the file:

    assert b'2024             ' == b'<T200020240A0000>'
    At index 0 diff: b'2' != b'<'

That is the collapsed composite emitting the four-character year and padding the
remaining thirteen bytes of AEAT's required constant to blanks. The red confirms
the defect independently of the reference document that reported it.

The red was observed before any declaration changed and is recorded here rather
than committed: a committed red gate would break every concurrent run in this
shared tree, so the proof is the observation, not a published failing state.

## Verification

<!-- Where the evidence is that something RAN, quote the instrument rather than
     summarising it: the invocation, then the runner's verbatim summary line.

         uv run --no-sync pytest <paths> -m integration -n 0
         15 passed in 10.35s

     The invocation shows the selection (marker expression and path scope); the
     summary line shows what that selection produced. A run that selected nothing
     exits zero and reads as green, so a paraphrase such as "the tests pass"
     discards exactly the part a reader needs. Quote, do not summarise. -->

Pre-fix run, against the unmodified registry declaration:

    uv run --no-sync pytest src/cadrumo/application/filing/tests/test_export.py::test_export_writes_the_modelo_200_envelope_tags_aeat_publishes -n0 -q
    1 failed in 13.28s

`-n0` is passed explicitly because the project's pytest configuration injects
`-n auto`, and a proof read from the controlling session must not be scattered
across worker processes.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
