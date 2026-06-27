---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S03'
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
     The S03 and 2026-06-26-binding-fold-in-carry-unification-plan placeholders are machine-filled by
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
     The vaultspec-standard-executor: enforce the typed relation op at registry-build via the section validator, rejecting an unknown op at build not resolve time and ## Scope

- `src/aeat/domain/calculations/registry/_validate_relation_sources.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# vaultspec-standard-executor: enforce the typed relation op at registry-build via the section validator, rejecting an unknown op at build not resolve time

## Scope

- `src/aeat/domain/calculations/registry/_validate_relation_sources.py`

## Description

- Enforce the typed relation op at registry-build via the strict `RelationAggregation.op` field: an unknown op is rejected when the `RelationDefinition` is constructed, earlier than the section validator, at parity with the binding op gate.
- Remove the now-redundant inline op-check from the relation section validator in `_validate_relation_sources.py`.

## Outcome

- Landed in the single atomic P01 commit `4b3311a02`. The build-time rejection is the strongest gate (construction-time), matching how `BindingAggregation` enforces binding ops. The committed-registry build validates clean.

## Notes

- The section-validator op-check became unreachable once the field is strictly typed (a relation that constructed successfully already carries a valid op), so it was deleted rather than left as dead defence-in-depth.
