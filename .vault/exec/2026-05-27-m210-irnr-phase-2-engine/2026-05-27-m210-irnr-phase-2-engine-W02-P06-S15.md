---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S15'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace m210-irnr-phase-2-engine with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-05-27-m210-irnr-phase-2-engine-plan placeholders are machine-filled by
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
     The add the anti-tautology test proving the Beckham IRPF base sums only the ES row, the DE row is emitted as a segregated issue with its jurisdiction preserved, and a gate-bypass mutant inflates the IRPF base by the DE row and ## Scope

- `src/aeat/application/aggregation` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add the anti-tautology test proving the Beckham IRPF base sums only the ES row, the DE row is emitted as a segregated issue with its jurisdiction preserved, and a gate-bypass mutant inflates the IRPF base by the DE row

## Scope

- `src/aeat/application/aggregation`

## Description

- Reconcile the real M151 aggregation test coverage to this historical Step.
- Verify the ES-versus-foreign source-scope witness and the preserved transaction identifier and jurisdiction on the segregation issue.

## Outcome

Completed by commit `24c43acfe8` under the dedicated Modelo 151 source-scope plan. The real-engine test mutates otherwise equivalent ES and FR rows: only ES contributes to the base, while the FR row produces a typed issue carrying its identifier and jurisdiction. The registry-binding test independently includes a DE foreign-source row, so the plan's non-ES witness is covered without coupling correctness to a single country example.

## Notes

No new production code was authored in this reconciliation Step.
