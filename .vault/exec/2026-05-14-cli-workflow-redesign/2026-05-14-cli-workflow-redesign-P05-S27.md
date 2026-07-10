---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S27'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-workflow-redesign with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S27 and 2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan placeholders are machine-filled by
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
     The Validate Modelo 145 help text avoids file, filing, deadline, live-read, and AEAT submission vocabulary and ## Scope

- `tests/entrypoints/cli` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Validate Modelo 145 help text avoids file, filing, deadline, live-read, and AEAT submission vocabulary

## Scope

- `tests/entrypoints/cli`

## Description

- Ground `P05.S27` from the current plan status, semantic search for the M145 forbidden-surface vocabulary, and the existing M145 group-help coverage.
- Expand the M145 CLI help test from group-only coverage to every visible help surface: group, create, validate, export, mark-delivered-to-payer, and mark-locally-completed.
- Check forbidden help words and phrases for filing, deadline, live-read, portal, AEAT submission, submit, receipt, shim, stub, fake-support, deprecated-spelling, and compatibility-alias vocabulary.
- Keep the check token-aware so unrelated words such as `profile` do not create false failures.

## Outcome

- `P05.S27` implementation is complete and ready for plan-row closure.
- Verification passed:
  - Focused ruff check for the S27 M145 CLI integration test update: passed.
  - Focused ruff format check for the S27 M145 CLI integration test update: passed.
  - M145 real CLI integration slice, including all six help-surface vocabulary checks: 11 passed.

## Notes

- No production-code change was required; current M145 command help already uses local payer communication vocabulary.
- The code review found no blocking issues for `P05.S27`.
