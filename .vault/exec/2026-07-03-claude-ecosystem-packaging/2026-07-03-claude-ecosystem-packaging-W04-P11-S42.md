---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S42'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace claude-ecosystem-packaging with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S42 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Document the full release checklist joining versioning, wheel build, name claim, grant and plugin/marketplace push in RELEASING.md and ## Scope

- `RELEASING.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Document the full release checklist joining versioning, wheel build, name claim, grant and plugin/marketplace push in RELEASING.md

## Scope

- `RELEASING.md`

## Description

- Document the full per-release checklist joining release-please versioning (including the `packaging/aeat_data` synced-version bump), the packaging-smoke and plugin-validate gates, the human-only push, both publishes, the plugin/marketplace regeneration + push, and the docs update hook.
- Record the deliberate out-of-scope items: Trusted Publishing (needs CI — operator-level policy decision) and any live AEAT interaction.
- Commit `3ebe536354`.

## Outcome

- One document carries the whole release lane end to end.

## Notes

Executed inline by the coordinator during the account rate-limit window.
