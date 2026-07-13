---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S09'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-terminology-search with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-07-13-docs-terminology-search-plan placeholders are machine-filled by
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
     The Run incremental reindex then the widened sweep through the resident service, wrangle through the typed resolution, and land the widened relevance mapping as a reviewed committed diff and ## Scope

- `src/cadrumo/_data/terminology/relevance/relevance.json` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run incremental reindex then the widened sweep through the resident service, wrangle through the typed resolution, and land the widened relevance mapping as a reviewed committed diff

## Scope

- `src/cadrumo/_data/terminology/relevance/relevance.json`

## Description

- Run the widened sweep through the resident service (incremental reindex
  first): 112 queries over 49 concepts, 0 failed.
- Review the mapping diff: 335 targets vs 247 (+89 gained, 1 lost - a tail
  legal target on the generic 'declaracion' query whose top-6 is unchanged;
  adjudicated acceptable).
- Land the widened relevance mapping and regenerate the coverage report.

## Outcome

Committed mapping: 112 queries / 335 targets. Coverage after widening:
concepts 49/49, legal 121/555 (21.8 percent, from 11 at wave start),
casillas 22/6330, 143 orphan grounding targets. Every new concept's own
card leads its queries; one ranking note recorded (the bare 'modelo 115'
query surfaces the 180 summary card first, its own card second).

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
