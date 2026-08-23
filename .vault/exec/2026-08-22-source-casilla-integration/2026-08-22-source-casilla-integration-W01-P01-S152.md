---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:80a442d6e1ff74084bc8dfbffa3307ef33dda94a773e52715d9e3f255dd7ac19'
step_id: 'S152'
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
     The S152 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The classify the M720 foreign-asset composite as grounding-blocked until a typed unique resolved-asset identity or separately approved uniqueness-enforced key exists and ## Scope

- `src/cadrumo/application/aggregation`
- `.vault` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# classify the M720 foreign-asset composite as grounding-blocked until a typed unique resolved-asset identity or separately approved uniqueness-enforced key exists

## Scope

- `src/cadrumo/application/aggregation`
- `.vault`

## Description

- Remove foreign-asset provenance that promoted upstream carrier identifiers to resolved-asset identities.
- Retain calculation outputs while refusing a fabricated primary.
- Preserve M720's grounding-blocked classification pending a typed unique asset identity.

## Outcome

Foreign-assets calculation remains available, but connectivity admission can no longer pass using an ungrounded synthetic identity.

## Notes

Implemented in shared-worktree commit `31e504c55b`. No composite key or weakened identity rule was introduced.
