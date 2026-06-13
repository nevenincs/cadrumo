---
tags:
  - '#exec'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-06-13'
step_id: 'S16'
related:
  - "[[2026-06-13-modelo-130-pagos-fraccionados-carry-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace modelo-130-pagos-fraccionados-carry with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# assert the Stage-1 prior_payment_not_deducted advisory degrades to fire only when a prior filing exists in the catalogue but its observation is unreadable/absent so the carry could not populate, and stays silent when the span binding resolves casilla 05 cleanly to non-zero

## Scope

- `src/aeat/application/modelo/tests/test_modelo_130_prior_payment_advisory.py`

## Description

- Confirmed the Stage-1 `prior_payment_not_deducted` advisory degrades naturally: its zero-casilla-05 precondition keeps it silent once the carry populates casilla 05, firing only when the carry genuinely could not run.
- Rewrote `test_modelo_130_prior_payment_advisory.py` to pin the post-Stage-2 behaviour: a 2T with a prior 1T filing auto-carries casilla 05 (over-payment advisory silent), a prior filing carrying casilla 16 fires neither advisory, and a 1T fires nothing.

## Outcome

The over-payment advisory stays silent when the carry resolves casilla 05 cleanly to non-zero; the not-captured minoración advisory fires only on the genuine gap. Verified by `test_modelo_130_prior_payment_advisory.py` (3 passed). Landed in commit `02e9bfb65`.

## Notes

The degradation required no change to the Stage-1 advisory firing logic; the bound carry populating casilla 05 satisfies the existing zero-precondition gate.
