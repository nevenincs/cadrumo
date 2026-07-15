---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S04'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

# Merge justificante-receipts.md into reconcile.md as a leading pull-and-store-the-justificante section

## Scope

- `sweep inbound links`
- `delete the merged page`
- `docs/how-to/reconcile.md docs/how-to/justificante-receipts.md`

## Description

- Rewrite `docs/how-to/reconcile.md`'s opening as the "This page covers the
  ..." paragraph spanning both concerns (the receipt and the comparison).
- Absorb `docs/how-to/justificante-receipts.md` as a leading "Pull and store
  the justificante" section: the standalone `aeat app live justificante
  pull`, the stored-capture fields, the encrypted-storage and supersession
  behaviour, and `list`/`view` inspection. The duplicated profile-creation
  aside and the duplicated auth-refusal paragraph were condensed into the
  shared Before-you-start and the pull section.
- Retarget internal references (what-to-keep-as-evidence, reconcile-pull
  storage note, Next steps) to the new section anchor; sweep the three
  external inbound references (`file-at-aeat.md`, the how-to index grid card
  and toctree) and fix `read-live-aeat-data.md`'s two links ahead of its own
  S05 retirement so this commit leaves no dangling link.
- Delete `docs/how-to/justificante-receipts.md` via `git rm`.

## Outcome

Pulling the receipt and reconciling against it are now one page in the order
the operator actually works (pull first, compare second). Grep confirms zero
remaining `justificante-receipts` references outside build artifacts.

## Notes

None.
