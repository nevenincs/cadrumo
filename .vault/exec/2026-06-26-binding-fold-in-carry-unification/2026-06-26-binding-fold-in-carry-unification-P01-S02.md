---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S02'
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
     The S02 and 2026-06-26-binding-fold-in-carry-unification-plan placeholders are machine-filled by
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
     The vaultspec-standard-executor: replace the three inline str(relation.aggregation).get('op') re-parses with the one binding_aggregation_op accessor at the requirement-keying and resolve sites and ## Scope

- `src/aeat/domain/calculations/registry/_relations.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# vaultspec-standard-executor: replace the three inline str(relation.aggregation).get('op') re-parses with the one binding_aggregation_op accessor at the requirement-keying and resolve sites

## Scope

- `src/aeat/domain/calculations/registry/_relations.py`

## Description

- Add one `relation_aggregation_op` accessor in `_relation_aggregation.py` (a new per-family module) returning the typed `RelationAggregationOp`, defaulting to COPY when a relation declares no aggregation, re-exported through the registry package facade.
- Replace the three inline `str((relation.aggregation or {}).get("op", ...))` re-parses with the accessor: the requirement-keying and resolve sites in `_relations.py`, and the M390 FIFO-partition discriminator in `_relation_prefill.py`.
- Scaffold the API docs stub for the new accessor module.

## Outcome

- Landed in the single atomic P01 commit `4b3311a02`. All three inline re-parses are gone; the relation op is read in one typed place. The M390 box-97/662 partition reads the typed op (COPY = last-period box 97, SUM = non-last box 662), self-documenting the FIFO partition.

## Notes

- The M390 partition discriminator's prior inline default was the empty string; the typed accessor defaults to COPY. Both M390 carry-box relations declare explicit ops, so the default is never relied on there and the classification is identical.
