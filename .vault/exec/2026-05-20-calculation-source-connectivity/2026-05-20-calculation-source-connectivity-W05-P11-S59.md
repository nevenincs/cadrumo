---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S59'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace calculation-source-connectivity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S59 and 2026-05-20-calculation-source-connectivity-plan placeholders are machine-filled by
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
     The Run architecture boundary audit for source mesh directionality and ## Scope

- `src/aeat/application/aggregation` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run architecture boundary audit for source mesh directionality

## Scope

- `src/aeat/application/aggregation`

## Description

- Run the architecture-boundary audit for source-mesh directionality via the `domain-not-application` import-linter contract and a grimp runtime import-graph pass over the aggregation surface.

## Outcome

PASS — no finding. The `domain-not-application` contract is KEPT over the full tree (3252 files, 15248 dependencies): no production domain module imports the application layer, so the mesh's hexagonal direction holds — registry resolvers/observation protocols stay in the domain, storage-reading source resolvers + mesh orchestration stay in the application layer. The grimp runtime graph confirms every domain→application edge is a test module / conftest (legitimate cross-layer test wiring), including the three `registry.tests → application.aggregation` edges; zero production directionality violation. Recorded in the campaign closeout audit.

## Notes

Both the import-linter contract and the grimp graph read the import graph, not a registry load, so this axis was unaffected by the concurrent modelo-145 registry churn and ran clean now.
