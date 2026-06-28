---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S10'
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
     The S10 and 2026-06-26-binding-fold-in-carry-unification-plan placeholders are machine-filled by
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
     The vaultspec-code-reviewer: VERIFICATION GATE 1-BEFORE - run the #1 M303 refunded-period zero-carry, #7 M390 box 97 prior-pending, and #12 M390 box 662 applied-credit regression gates and record the baseline casilla values before any carry-reconciliation edit and ## Scope

- `src/aeat/application/calculations/tests/test_modelo_303_refunded_period_carry.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# vaultspec-code-reviewer: VERIFICATION GATE 1-BEFORE - run the #1 M303 refunded-period zero-carry, #7 M390 box 97 prior-pending, and #12 M390 box 662 applied-credit regression gates and record the baseline casilla values before any carry-reconciliation edit

## Scope

- `src/aeat/application/calculations/tests/test_modelo_303_refunded_period_carry.py`

## Description

- Verification gate 1 (before): run the #1 M303 refunded-period zero-carry, #7 M390 box-97 prior-pending, and #12 M390 box-662 applied-credit regression gates plus the pull-vs-calculate parity and cross-period clean-state surfaces, capturing the baseline before any carry-reconciliation edit.

## Outcome

- Baseline captured green at HEAD before the P03 edit: 66 tests passed across the carry gates, parity, cross-period clean-state, and the perceptor-count surface.

## Notes

- No code change in this gate Step; it records the pre-edit baseline the after-gate (S13) asserts against.
