---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S08'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace conformance-cli with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-07-27-conformance-cli-plan placeholders are machine-filled by
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
     The re-point the export completeness and fichero-BOE parity tests at the shared required-set derivation, removing the mirrored duplicate and ## Scope

- `src/cadrumo/application/filing/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# re-point the export completeness and fichero-BOE parity tests at the shared required-set derivation, removing the mirrored duplicate

## Scope

- `src/cadrumo/application/filing/tests`

## Description

- In `test_export_completeness_gate.py`: added `required_applicable_casilla_ids` to the `_export` import; replaced the `_required_applicable` helper body (which re-derived the set comprehension verbatim with an "Mirror the gate's required set" comment) with a thin delegate calling the shared function. Changed return type annotation from `set[CasillaId]` to `frozenset[CasillaId]` to match the shared function.
- In `test_fichero_boe_completeness_parity.py`: added `required_applicable_casilla_ids` to the `_export` import; replaced the inline three-line set comprehension in `test_complete_draft_reaches_disk_for_every_required_casilla` (including its "Mirror the gate's required set" comment) with a single call to the shared function.

## Outcome

Both test modules compile cleanly and all 12 tests pass. Mutation-flip evidence: temporarily corrupting `required_applicable_casilla_ids` to return `frozenset()` caused 3 failures — `test_thin_fixed_width_draft_panics_before_writing[modelo-130]`, `test_thin_fixed_width_draft_panics_before_writing[modelo-390]`, and `test_complete_draft_reaches_disk_for_every_required_casilla` — confirming the tests are non-vacuous. Reverting the mutation restores 12 passed. Commit: `9c64ec0d99`.

## Notes

Landed in the same commit as S07 because the test re-pointing depends on the extraction.
