---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S12'
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
     The S12 and 2026-06-26-binding-fold-in-carry-unification-plan placeholders are machine-filled by
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
     The vaultspec-high-executor: reconcile the derive_303_compensation_available carry path onto the one wallet authority so the M390 box 97/662 FIFO partition derives from the one projection (apply-cached on collision) and ## Scope

- `src/aeat/domain/iva_compensation/_carry_forward.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# vaultspec-high-executor: reconcile the derive_303_compensation_available carry path onto the one wallet authority so the M390 box 97/662 FIFO partition derives from the one projection (apply-cached on collision)

## Scope

- `src/aeat/domain/iva_compensation/_carry_forward.py`

## Description

- Reconcile the `derive_303_compensation_available` carry path and the M390 box-97/662 FIFO partition onto the one wallet authority, so the M390 partition derives from the one projection.

## Outcome

- No code change required: analysis confirmed `derive_303_compensation_available` and `derive_iva_compensation_year_end_carry_partition` are shared carry arithmetic that already feed/defer to the wallet. `derive_303` computes the disponible casilla value stored on a filed observation, which the IVA-compensation-history projection reads to reconstruct the local recurrence the wallet reconciliation consumes; the M390 partition is consumed by the box-97/662 binding path (preserved via the P01 typed relation op). Neither is a parallel route to the wallet-owned compensación binding, so neither was changed.

## Notes

- Changing these pure carry computations would have been unnecessary churn on the highest-risk layer. The C3 fragmentation was the single back-door observation injection removed in S11; once removed, the wallet is the single authority and these paths already feed it. The M390 FIFO box-97/662 identity is preserved exactly.
