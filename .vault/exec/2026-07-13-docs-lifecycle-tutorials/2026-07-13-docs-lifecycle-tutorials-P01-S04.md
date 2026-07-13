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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-lifecycle-tutorials with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-07-13-docs-lifecycle-tutorials-plan placeholders are machine-filled by
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
     The Merge justificante-receipts.md into reconcile.md as a leading pull-and-store-the-justificante section and ## Scope

- `sweep inbound links`
- `delete the merged page`
- `docs/how-to/reconcile.md docs/how-to/justificante-receipts.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
