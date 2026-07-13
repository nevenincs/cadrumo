---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S05'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-lifecycle-tutorials with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S05 and 2026-07-13-docs-lifecycle-tutorials-plan placeholders are machine-filled by
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
     The Retire read-live-aeat-data.md, redistributing its live-pull content to check-aeat-notifications.md, censo-update.md, and reconcile.md and ## Scope

- `sweep inbound links`
- `docs/how-to/read-live-aeat-data.md docs/how-to/check-aeat-notifications.md docs/how-to/censo-update.md docs/how-to/reconcile.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Retire read-live-aeat-data.md, redistributing its live-pull content to check-aeat-notifications.md, censo-update.md, and reconcile.md

## Scope

- `sweep inbound links`
- `docs/how-to/read-live-aeat-data.md docs/how-to/check-aeat-notifications.md docs/how-to/censo-update.md docs/how-to/reconcile.md`

## Description

- Add a "How a live read works" section to
  `docs/how-to/check-aeat-notifications.md` absorbing the retired page's
  durable signal: the uniform read-only pull-to-encrypted-local-copy pattern,
  the apply-nothing-automatically rule, the boundary cross-link, the
  auth-preflight refusal explanation (Cl@ve message vs real cause), and the
  `AEAT_LIVE_TESTS_ENABLED` developer-setting note; add the "This page covers
  the ..." opening.
- Point the censo and justificante surfaces at their own guides
  (`censo-update.md`, `reconcile.md#pull-and-store-the-justificante`) instead
  of re-listing their commands.
- Sweep inbound references: the how-to index grid card and toctree entry
  removed, `runbooks/RB-002-live-read-refused.md` retargeted to
  `check-aeat-notifications.md`.
- Delete `docs/how-to/read-live-aeat-data.md` via `git rm`.

## Outcome

The thin live-read index page is retired; its unique content lives on the
page that actually lists the live commands. Grep confirms zero remaining
`read-live-aeat-data` references outside build artifacts.

## Notes

`censo-update.md` needed no addition: the review-then-apply pattern the
retired page described is already that guide's core workflow.
