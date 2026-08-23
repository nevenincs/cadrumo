---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:5c71b5ceeacd9b869ef3668789cd2c69f42d5786f341b189102c8055a34e4868'
step_id: 'S149'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S149 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The define the canonical primary/contributor lineage role and replace the calculation-source provenance shape atomically with separate resolved and contributor axes and ## Scope

- `src/cadrumo/core`
- `src/cadrumo/domain/modelos` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# define the canonical primary/contributor lineage role and replace the calculation-source provenance shape atomically with separate resolved and contributor axes

## Scope

- `src/cadrumo/core`
- `src/cadrumo/domain/modelos`

## Description

- Add the closed `CalculationSourceLineageRole` vocabulary at the shared core boundary.
- Replace persisted provenance with explicit resolved-source, contributor, role, reference, parent, and fingerprint axes.
- Make every lineage axis participate in calculation revision identity.
- Reject illegal primary parents, missing contributor parents, duplicate primary references, and orphaned edges.

## Outcome

The canonical application and domain carriers now express direct and composite source graphs without conflating resolver ownership with upstream taxonomy.

## Notes

Implemented in shared-worktree commit `31e504c55b`. A local follow-up makes graph validation run for merged composite resolutions too. That shared commit also contains unrelated concurrent registry tests; no peer changes were reverted.
