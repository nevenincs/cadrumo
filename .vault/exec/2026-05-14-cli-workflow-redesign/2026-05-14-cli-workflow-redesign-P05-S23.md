---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S23'
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
     The S23 and 2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan placeholders are machine-filled by
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
     The Add Modelo 145 command handlers that delegate to the backend communication service and ## Scope

- `src/aeat/entrypoints/cli` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add Modelo 145 command handlers that delegate to the backend communication service

## Scope

- `src/aeat/entrypoints/cli`

## Description

- Ground `P05.S23` from the current plan status, the Modelo 145 reopen ADR/research, semantic search for the CLI/backend communication surfaces, and grep/readback of the existing Modelo 036 command-registration analogue.
- Add the `m145` Typer subgroup under `app modelo` with the five accepted backend communication actions: `create`, `validate`, `export`, `mark-delivered-to-payer`, and `mark-locally-completed`.
- Keep handlers thin by parsing CLI tokens at the Typer boundary, resolving the active bucket and actor through existing helpers, and delegating create/validate/export/transition work to the backend Modelo 145 communication service.
- Add registered OutputSchema payloads for the new `modelo.m145.*` command paths and a manifest guard proving the payload-discovery loader indexes the new module naming shape.
- Add real CLI tests that create a Modelo 145 communication record, validate it, export the registry-backed payload, and drive payer-delivery and local-completion transitions through the actual backend service.
- Record the S23 code-review pass in the existing `cli-workflow-redesign` audit document.

## Outcome

- `P05.S23` implementation is complete and ready for plan-row closure.
- Verification passed:
  - Focused ruff check for the S23 CLI registration, payload, and test files: passed.
  - Focused ruff format check for the S23 CLI registration, payload, and test files: passed.
  - M145 CLI integration slice plus manifest and schema-leaf checks: 6 passed.
  - M145 backend communication create/validate/export/transition slice: 21 passed.

## Notes

- The direct pytest path initially collected no tests because the repository default marker filter is `unit`; the CLI test module remains correctly marked as `integration` and was verified with `-m integration`.
- The code review found no blocking issues for `P05.S23`.
