---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S08'
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
     The S08 and 2026-06-26-binding-fold-in-carry-unification-plan placeholders are machine-filled by
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
     The vaultspec-code-reviewer: VERIFICATION GATE 5b - run full-calc, cross-period-continuity, and oracle suites after the fold-helper collapse and assert NO casilla value shifts with M130 and M353 shapes byte-identical and ## Scope

- `src/aeat/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# vaultspec-code-reviewer: VERIFICATION GATE 5b - run full-calc, cross-period-continuity, and oracle suites after the fold-helper collapse and assert NO casilla value shifts with M130 and M353 shapes byte-identical

## Scope

- `src/aeat/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py`

## Description

- Verification gate 5b: run the full-calc, cross-period-continuity, and oracle surfaces after the fold-helper collapse (S06 plus S07) and assert NO casilla value shifts, with the M130 prior_pagos and M353 per_grupo_member shapes preserved.

## Outcome

- The full registry plus calculations suites passed (3253 tests), unchanged from the S05 baseline; the M130 casilla-05 carry, M390 FIFO, M303 refunded-period, and pull-vs-calculate parity gates passed; collect-only clean. No casilla value shifted across S06 or S07.

## Notes

- No code change in this gate Step; it is a verification barrier. Both fold collapses are value-preserving by construction (the gather and the copy/sum arithmetic are byte-for-byte the prior logic, single-sourced), so the suite parity confirms the dedup introduced no shift.
