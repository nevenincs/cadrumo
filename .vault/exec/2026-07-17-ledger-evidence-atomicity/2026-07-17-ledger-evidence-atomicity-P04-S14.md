---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S14'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ledger-evidence-atomicity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S14 and 2026-07-17-ledger-evidence-atomicity-plan placeholders are machine-filled by
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
     The Regenerate the operator how-to and reference pages for ledger evidence from the frozen live surface and ## Scope

- `docs/how-to/ledger-evidence.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Regenerate the operator how-to and reference pages for ledger evidence from the frozen live surface

## Scope

- `docs/how-to/ledger-evidence.md`

## Description

- Correct the `ledger-evidence` how-to: the pull-folder step no longer offers `aeat app ledger link` as an evidence-binding alternative (link is invoice-only); fetched evidence binds via `aeat app ledger attach --attachment-id`.
- Confirm the generated CLI reference pages (`docs/cli/app/ledger.rst`, `cli-tree.json`) are gitignored build artefacts that regenerate against the live surface — no committed reference edit is needed, and their residual `--evidence-id` mentions belong to the retained `ledger evidence extract` command, not `link`.

## Outcome

- The ledger-evidence how-to is accurate against the frozen live surface: attach is the sole evidence door; link binds a reconciliation-catalogue invoice only. Documented-command conformance green on this surface (350 passed; the one failure is exec-authcert-p04's `config rekey` .seq). Commit `96bdc97ed9`.

## Notes

- The other forced how-to change (the import-bank-statements `link --evidence-id` paragraph + its `.seq`) landed with S07. This step's remaining scope was the pull-folder line and confirming the reference pages regenerate.
