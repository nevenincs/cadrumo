---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S06'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace fichero-boe-parity-gate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-07-01-fichero-boe-parity-gate-plan placeholders are machine-filled by
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
     The Unit-test the rendered-set enumeration across CASILLA, BINDING-row and COMPUTED field kinds and ## Scope

- `src/aeat/application/filing/tests/test_export_rendered_casilla_set.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Unit-test the rendered-set enumeration across CASILLA, BINDING-row and COMPUTED field kinds

## Scope

- `src/aeat/application/filing/tests/test_export_rendered_casilla_set.py`

## Description

- Add `test_export_completeness_sets.py` cases: the representable set covers every non-suppressed CASILLA field; the rendered set equals `representable ∩ draft.values` and is a subset of representable; dropping a required casilla from the draft removes it from the rendered set (the thin-file signal at the derivation level).

## Outcome

Four tests pass (90s). Ruff clean.

## Notes

One first-pass failure was a test-assumption bug, not a helper bug: the initial assertion computed the CASILLA-field set over all records, ignoring disposition suppression, so it disagreed with the helper (130 carries a suppressed DID page under a non-refund header). Fixed by mirroring `_did_page_suppressed` in the expected-set computation. The helper was correct.
