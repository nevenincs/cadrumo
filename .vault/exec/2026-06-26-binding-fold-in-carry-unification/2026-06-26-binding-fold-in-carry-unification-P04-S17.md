---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S17'
related:
  - "[[2026-06-26-binding-fold-in-carry-unification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-fold-in-carry-unification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S17 and 2026-06-26-binding-fold-in-carry-unification-plan placeholders are machine-filled by
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
     The vaultspec-code-reviewer: assert the live EnrollmentRecorder remains intact and importable through the top-level __all__ re-export and the full collect-only gate is clean after the orphan deletion and ## Scope

- `src/aeat/application/calculations/tests/test_multi_year.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# vaultspec-code-reviewer: assert the live EnrollmentRecorder remains intact and importable through the top-level __all__ re-export and the full collect-only gate is clean after the orphan deletion

## Scope

- `src/aeat/application/calculations/tests/test_multi_year.py`

## Description

- Assert the live `EnrollmentRecorder` (and the co-located `EnrollmentEvidence` / `EnrollmentYearObservation` / `EnrollmentEvidenceError` / `assert_enrollment_matches_manifest`) and the live `PreviousFilingSourceResolver` remain intact and importable through the package re-export after the orphan deletion, and that the full collect-only gate is clean.

## Outcome

- The live concerns import cleanly through the package facade; `MultiYearResolver` correctly raises `ImportError`. collect-only is clean. The source-resolver enrollment gate accepts the now-empty known-non-mesh inventory, `test_carry_gate_parity` (the live-path R2 coverage) passes, and the full calculations plus M390 FIFO plus retenciones suites pass (424 tests). No casilla value shifted.

## Notes

- The R2 carry-gate coverage that the two deleted `MultiYearResolver` tests provided is preserved by the live-path tests in `test_carry_gate_parity` (the `_revision_prefill_divergence` gate across the matching / divergent / missing / indeterminate outcomes), so removing the redundant secondary coverage lost no enforcement.
