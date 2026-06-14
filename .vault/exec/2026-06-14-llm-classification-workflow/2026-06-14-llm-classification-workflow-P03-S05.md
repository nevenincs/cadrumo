---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S05'
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
     The S05 and 2026-06-14-llm-classification-workflow-plan placeholders are machine-filled by
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
     The Real-behaviour tests: no-split verdict, in-place apply, auto-split route, recommendation Notice and ## Scope

- `src/aeat/application/ledger/tests`
- `src/aeat/entrypoints/cli/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Real-behaviour tests: no-split verdict, in-place apply, auto-split route, recommendation Notice

## Scope

- `src/aeat/application/ledger/tests`
- `src/aeat/entrypoints/cli/tests`

## Description

- Add no-split-verdict, in-place-apply, and multi-child-refusal tests to the evidence-split application suite.
- Add a CLI auto-split + recommendation-Notice integration test file (real CLI, real persistence, DI proposer; no mocks).

## Outcome

10 application split tests and 6 CLI auto-split tests green; 165 LLM/domain/CLI tests pass with no regressions.

## Notes

Tests live under domain tests/ folders per tests-live-under-domain-tests-folders.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
