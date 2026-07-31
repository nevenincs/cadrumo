---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:01d701797242f58cb8d12709f69b5ba15f80183bc4e530e3b1688eb9cfc4357b'
step_id: 'S02'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

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
