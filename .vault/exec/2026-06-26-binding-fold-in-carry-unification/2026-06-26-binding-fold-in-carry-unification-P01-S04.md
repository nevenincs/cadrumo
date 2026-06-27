---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S04'
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
     The S04 and 2026-06-26-binding-fold-in-carry-unification-plan placeholders are machine-filled by
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
     The vaultspec-code-reviewer: VERIFICATION GATE 5a - run full-calc, cross-period-continuity, and oracle suites after the relation-op typing and assert NO casilla value shifts and binding-aggregation-is-typed conformance green and ## Scope

- `src/aeat/domain/calculations/registry/tests/test_modelo_303_registry.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# vaultspec-code-reviewer: VERIFICATION GATE 5a - run full-calc, cross-period-continuity, and oracle suites after the relation-op typing and assert NO casilla value shifts and binding-aggregation-is-typed conformance green

## Scope

- `src/aeat/domain/calculations/registry/tests/test_modelo_303_registry.py`

## Description

- Verification gate 5a: run the full-calc, cross-period-continuity, and oracle suites after the relation-op typing and assert NO casilla value shifts plus binding-aggregation-is-typed conformance green.
- Update `test_modelo_390_registry` to assert the typed op via `relation_aggregation_op` against the enum members instead of the prior dict shape.

## Outcome

- The full registry plus calculations plus core suites passed (3664 tests), unchanged baseline; the #1 refunded-period, #7/#12 M390 FIFO, pull-vs-calculate parity, cross-period clean-state, M180/190/193, and test_binding_aggregation gates passed; collect-only clean; ruff clean. No casilla value shifted.

## Notes

- One test (`test_modelo_390_declares_annual_compensation_result_fields`) asserted the old `{"op": ...}` dict shape and was migrated to the typed-member assertion via the accessor, per the rule that tests assert against enum members.
