---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S13'
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
     The S13 and 2026-06-26-binding-fold-in-carry-unification-plan placeholders are machine-filled by
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
     The vaultspec-code-reviewer: VERIFICATION GATE 1-AFTER - re-run the #1 M303 refunded-period, #7 M390 box 97, and #12 M390 box 662 regression gates after each carry-reconciliation sub-step and assert ZERO casilla value shifts against the recorded baseline and ## Scope

- `src/aeat/application/modelo/tests/test_modelo_390_fifo_carried_pending.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# vaultspec-code-reviewer: VERIFICATION GATE 1-AFTER - re-run the #1 M303 refunded-period, #7 M390 box 97, and #12 M390 box 662 regression gates after each carry-reconciliation sub-step and assert ZERO casilla value shifts against the recorded baseline

## Scope

- `src/aeat/application/modelo/tests/test_modelo_390_fifo_carried_pending.py`

## Description

- Verification gate 1 (after): re-run the #1 M303 refunded-period, #7 M390 box-97, and #12 M390 box-662 regression gates plus the pull-vs-calculate parity and cross-period clean-state surfaces after the carry-reconciliation edit, and assert ZERO casilla value shifts against the recorded baseline.

## Outcome

- After-gate green and byte-identical to the S10 baseline: 66 tests passed across the same surfaces. The full calculations, iva_compensation, filed-capture, and wallet-engine integration suites also passed (456 tests). No casilla value shifted from the back-door-injection removal.

## Notes

- The R2 carry-trust layer (`revision_carry_outcome`, the clean-state evidence gate) was confirmed untouched; the P03 change is purely the value-layer injection removal beneath the trust layer.
