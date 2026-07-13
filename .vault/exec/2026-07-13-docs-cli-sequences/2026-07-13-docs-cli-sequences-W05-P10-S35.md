---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S35'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-cli-sequences with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S35 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Verify the tutorial sequences execute and match their goldens, the @result @expect asserts success, and the page renders stepped with content-identical no-JS output and ## Scope

- `docs/tutorials` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Verify the tutorial sequences execute and match their goldens, the @result @expect asserts success, and the page renders stepped with content-identical no-JS output

## Scope

- `docs/tutorials`

## Description

- Run the sequence-golden pytest gate `dev/docs/tests/test_sequence_goldens.py -m "integration and docs"`; the unscoped `check_sequences` half re-executes the two committed goldens against live output. 9 passed.
- Run the documented-command conformance gate `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py -m integration`; it scans the page's directive frames for verb-path and option-name validity and enforces the enrolled-page no-plain-fence tier. 57 passed.
- Run the changed-page nitpicky build `python -m dev.docs.build docs/how-to/first-quarterly-filing.md`; the `builder-inited` check hook re-executes both sequences and the directive renders both from their committed goldens. Build succeeded, exit 0.
- Confirm the four relative cross-links resolve (`modelo-130`, `classify-transactions`, `filing-spine`, `file-at-aeat` all exist under `docs/how-to/`).

## Outcome

All gates green. Both sequences execute hermetically and match their committed goldens; the `modelo-130-first-quarter` `@result` frame asserts `granted_verificado_completo == true` (a genuine success, not a reproduced failure); the page renders the server-side static transcript that the vendored widget progressively enhances.

## Notes

- The changed-page build emitted 6 `myst.xref_missing` warnings for the relative cross-links; these are single-page-build artifacts (the linked pages are absent from a one-page build) and resolve in a full-tree build where the target pages exist — verified each target file is present.
- The full-tree nitpicky `-n -W` build (a tens-of-minutes gate) was not run in full; the changed-page validation build is the ADR-designed incremental surface for exactly this and passed. The widget/no-JS degradation contract is covered green by the W04 `test_docs_build.py` sequence-widget tests, which exercise the same directive this page uses.
