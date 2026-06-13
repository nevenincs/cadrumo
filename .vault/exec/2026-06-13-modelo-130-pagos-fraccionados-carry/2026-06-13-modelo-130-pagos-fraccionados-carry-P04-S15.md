---
tags:
  - '#exec'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-06-13'
step_id: 'S15'
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

# add a parity-style regression proving the casilla-15 single-offset op=copy carry and the casilla-05 expanding-span op=sum carry both resolve correctly on a shared multi-quarter fixture, so the selector extension does not regress the modelo-130-relation-regression guarantees

## Scope

- `src/aeat/application/calculations/tests/test_modelo_130_carry_forward_continuity.py`

## Description

- Added `test_casilla_15_copy_and_casilla_05_sum_carries_resolve_on_shared_fixture` to `test_modelo_130_carry_forward_continuity.py`: a shared 1T/2T fixture (1T 07=+500/16=60, 2T 07=+300/16=40/saldo=150) at a 3T target.
- Asserted the casilla-15 single-offset op=copy carry resolves to the 2T saldo (150) and the casilla-05 expanding-span op=sum carry resolves to the independently-computed identity (700).

## Outcome

Both carries coexist on one fixture; the selector extension does not regress the casilla-15 single-offset carry (modelo-130-relation-regression guarantee). Landed in commit `53de169cb`.

## Notes

The casilla-05 value is asserted against an independent identity computed in-test, a different code path than the binding.
