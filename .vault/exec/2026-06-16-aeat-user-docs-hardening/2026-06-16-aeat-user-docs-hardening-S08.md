---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S08'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace aeat-user-docs-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden correct-ledger-entries.md and ## Scope

- `docs/how-to/correct-ledger-entries.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden correct-ledger-entries.md

## Scope

- `docs/how-to/correct-ledger-entries.md`

## Description

- Verify-close: read `correct-ledger-entries.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M11 (`split` -> `merge` broken at the seam): the split verb now emits the child transaction ids that `merge --child-id` requires, so the documented undo path is completable; the page documents `ledger split` with `--child-amount`/`--child-description` and the merge-back path.
- Confirm the update / archive / stash lifecycle verbs and their active-transaction refusals are documented.

## Outcome

- Page verified compliant at HEAD; finding M11 resolved (split child-id emission fixed 2026-06-19; `_ledger_lifecycle_cli.py` + payload). Delta: none required.

## Notes

- Residual m12 (stash/archive print no lifecycle status) is an APP-side ergonomics finding, out of documentation scope. CLI conformance gate green.
