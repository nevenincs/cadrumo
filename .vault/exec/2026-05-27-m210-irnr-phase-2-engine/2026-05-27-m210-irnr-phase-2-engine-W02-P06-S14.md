---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S14'
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
     The S14 and 2026-05-27-m210-irnr-phase-2-engine-plan placeholders are machine-filled by
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
     The add the per-row segregation gate in the M151 classifier so a row with `source_jurisdiction != "ES"` produces a `BECKHAM_FOREIGN_SOURCE_SEGREGATED` issue rather than a base observation, anchored on LIRPF Art 93.5 and ## Scope

- `src/aeat/application/aggregation` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add the per-row segregation gate in the M151 classifier so a row with `source_jurisdiction != "ES"` produces a `BECKHAM_FOREIGN_SOURCE_SEGREGATED` issue rather than a base observation, anchored on LIRPF Art 93.5

## Scope

- `src/aeat/application/aggregation`

## Description

- Reconcile the completed M151 per-row Spanish-source segregation classifier to this historical Step.
- Verify that non-Spanish and unresolved jurisdictions become typed audit-visible issues rather than base observations.

## Outcome

Completed by commit `24c43acfe8` under the dedicated Modelo 151 source-scope plan. The classifier admits only `source_jurisdiction == "ES"` and emits `BECKHAM_FOREIGN_SOURCE_SEGREGATED` with the rejected code for a foreign row. The classifier-based shape is the architect-approved decision recorded by the source-jurisdiction closing review.

## Notes

No new production code was authored in this reconciliation Step.
