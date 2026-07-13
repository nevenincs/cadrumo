---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S02'
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
     The S02 and 2026-07-13-docs-lifecycle-tutorials-plan placeholders are machine-filled by
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
     The Merge review-queue.md into classify-transactions.md as a what-still-needs-a-decision subsection and ## Scope

- `sweep inbound links`
- `delete the merged page`
- `docs/how-to/classify-transactions.md docs/how-to/review-queue.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Merge review-queue.md into classify-transactions.md as a what-still-needs-a-decision subsection

## Scope

- `sweep inbound links`
- `delete the merged page`
- `docs/how-to/classify-transactions.md docs/how-to/review-queue.md`

## Description

- Add the "This page covers the ..." opening paragraph to
  `docs/how-to/classify-transactions.md`, naming the queue among the page's
  concerns.
- Absorb `docs/how-to/review-queue.md` as a new "See everything that still
  needs a decision" section placed before "Confirm readiness": the
  profile-wide queue concept, list/narrow/inspect commands, the accepted
  `--kind` token set, the `--explain` legal grounding and JSON `legal_refs`
  note, and the what-clears-each-kind summary condensed to one paragraph with
  the existing cross-links.
- Sweep the three inbound references: the how-to index grid card removed, the
  index toctree entry removed, `filing-readiness.md` retargeted to the new
  section anchor.
- Delete `docs/how-to/review-queue.md` via `git rm`.

## Outcome

The queue now lives where transaction decisions are made instead of as a
standalone page. Grep confirms zero remaining `review-queue` references
outside build artifacts.

## Notes

The queue also covers invoice and modelo-finding kinds; their resolving pages
(`ledger-evidence.md`, `verification-reports.md`) remain cross-linked from the
new section, so no signal was dropped in the condensation.
