---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S10'
related:
  - "[[2026-06-14-llm-classification-workflow-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace llm-classification-workflow with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S10 and 2026-06-14-llm-classification-workflow-plan placeholders are machine-filled by
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
     The Real-behaviour tests for reject (event recorded, no mutation, history/view) and ## Scope

- `locales`
- `how-to review-loop section`
- `src/aeat/application/ledger/tests`
- `src/aeat/entrypoints/cli/tests`
- `src/aeat/locales`
- `docs/how-to/classify-with-llm.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Real-behaviour tests for reject (event recorded, no mutation, history/view)

## Scope

- `locales`
- `how-to review-loop section`
- `src/aeat/application/ledger/tests`
- `src/aeat/entrypoints/cli/tests`
- `src/aeat/locales`
- `docs/how-to/classify-with-llm.md`

## Description

- Add 5 application reject tests (event recorded, no mutation, saturated/split capture, unknown/non-active refusals) and 3 CLI reject tests (records-event, reject/apply exclusivity, auto-split reject).
- Add reject locale keys via the aeat.locales CLI; document the four-terminal loop in the classify-with-llm how-to.

## Outcome

All reject tests green; locale parity/honesty and documented-command conformance clean.

## Notes

Tests are real-behaviour (real persistence, DI proposers, no mocks).

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
