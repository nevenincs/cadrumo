---
tags:
  - '#exec'
  - '#modelo-localization-cascade'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:b4df30928e80e15ce973233185d114372ca83da3aa34700d356402a499e31ba0'
step_id: 'S13'
related:
  - "[[2026-08-04-modelo-localization-cascade-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace modelo-localization-cascade with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S13 and 2026-08-04-modelo-localization-cascade-plan placeholders are machine-filled by
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
     The Record every mismatch and candidate continuity decision as an explicit review disposition and ## Scope

- `dev/registry/migration` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Record every mismatch and candidate continuity decision as an explicit review disposition

## Scope

- `dev/registry/migration`

## Description

- Record all current equal-to-source values by locale and semantic source.
- Record the 64 Spanish Modelo values as official source text rather than translation debt.
- Record the 33 Hungarian M100 `Index` dispositions through the locale CLI allowlist.

## Outcome

Resolved by the 2026-08-05 identical-source adjudication research and
`src/cadrumo/locales/_intentional_identical.json`. The current inventory has
zero unresolved equality candidates: generic Catalan 30, generic Spanish 51,
Spanish Modelo source 64, and Hungarian 63, including 33 M100 `Index` keys.

## Notes

Spanish source values were preserved verbatim. No semantic claim was inferred
from English equality alone; continuity and wording conflicts remain bounded
manual review items.
