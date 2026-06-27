---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S06'
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
     The S06 and 2026-06-26-binding-fold-in-carry-unification-plan placeholders are machine-filled by
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
     The vaultspec-high-executor: collapse the three near-identical observation-folding loops onto the one fold helper from the phase-2.2 resolver contract, preserving the M130 direct-carry and M353 per_grupo_member output shapes exactly (apply-cached on collision, peer-WIP likely) and ## Scope

- `src/aeat/application/calculations/_relation_prefill.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# vaultspec-high-executor: collapse the three near-identical observation-folding loops onto the one fold helper from the phase-2.2 resolver contract, preserving the M130 direct-carry and M353 per_grupo_member output shapes exactly (apply-cached on collision, peer-WIP likely)

## Scope

- `src/aeat/application/calculations/_relation_prefill.py`

## Description

- Extract the byte-identical relation observation-fold logic, duplicated as `_observed_requirement_values` in both the application relation prefill and the domain relations module, into one shared helper module `_observation_fold.py` in the domain registry package.
- Expose `gather_observed_requirement_values` (match one observed filing per source period, extract the source casilla), `fold_observed_requirement_values` (copy/sum to one Decimal), and `resolve_observed_requirement_value` (gather plus fold), re-exported through the registry package facade.
- Delete the application twin's `_resolve_requirement_value` and its local gather in favour of `resolve_observed_requirement_value`; delete the domain twin's local gather in favour of `gather_observed_requirement_values`, keeping its two-stage `resolve_relation_values` fold so the public domain contract and its validation stay byte-identical.
- Scaffold the API docs stub for the new module.

## Outcome

- One commit `a52f1317e` (`relocation:observation-fold-helper`), 6 files. No casilla value shifts: the gather and fold are byte-for-byte the prior logic, now single-sourced. The full registry plus calculations suites passed (3253 tests, unchanged baseline); the relation-fold and pull-vs-calculate parity surfaces passed (125 tests); collect-only clean.

## Notes

- The reference named the application source mesh as the helper home; that is architecturally impossible for the domain twin (domain cannot import application). The domain registry package is the boundary-correct home, and the fold is pure domain logic. Recorded as an autonomous architecture correction, not a value-affecting choice.
- The shared error text adopts the more informative domain form (carrying the relation ids); no test pins the prior application-path text.
