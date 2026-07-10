---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S16'
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
     The S16 and 2026-05-27-m210-irnr-phase-2-engine-plan placeholders are machine-filled by
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
     The architect-2 selects classifier-based vs predicate-based shape, determining the S10/S11 and S13/S14 sites (if predicate-based, author a new operator following the S376/S377/S378 pattern, otherwise close as a no-op affirming the classifier-based Steps) and ## Scope

- `src/aeat/application/modelo/_verification_predicates.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# architect-2 selects classifier-based vs predicate-based shape, determining the S10/S11 and S13/S14 sites (if predicate-based, author a new operator following the S376/S377/S378 pattern, otherwise close as a no-op affirming the classifier-based Steps)

## Scope

- `src/aeat/application/modelo/_verification_predicates.py`

## Description

- Reconcile the recorded architect verdict on the source-jurisdiction gate shape.
- Confirm that the classifier-based option is selected and that no registry-predicate operator is required for this work.

## Outcome

The classifier-based shape is selected. The source-jurisdiction research and the cross-domain continuity closing review reject a registry predicate because it loses per-row provenance and produces opaque aggregate refusals. The completed M151 implementation follows this shape; a future M210 implementation must use the same classifier-and-typed-issue contract.

## Notes

This is an architecture-decision reconciliation record. No new production code was authored.
