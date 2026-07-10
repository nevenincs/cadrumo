---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S26'
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
     The S26 and 2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan placeholders are machine-filled by
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
     The Route Modelo 145 command failures through the central command error boundary and ## Scope

- `src/aeat/entrypoints/cli` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Route Modelo 145 command failures through the central command error boundary

## Scope

- `src/aeat/entrypoints/cli`

## Description

- Ground `P05.S26` from the current plan status, semantic search for the CLI error boundary, the decorated Typer tree wiring, and the registered M145 service error-code rows.
- Confirm M145 service exceptions already inherit from the central `AeatError` hierarchy and are registered with stable error codes.
- Add real CLI integration coverage for missing-record validation and invalid local-completion transition failures.
- Assert those failures render through the central JSON error envelope, carry the M145 error codes and categories, and do not leak tracebacks.
- Leave parser, renderer, backend validation, export, persistence, event, and state-transition semantics unchanged.

## Outcome

- `P05.S26` implementation is complete and ready for plan-row closure.
- Verification passed:
  - Focused ruff check for the S26 CLI integration test update: passed.
  - Focused ruff format check for the S26 CLI integration test update: passed.
  - M145 real CLI integration slice, including central error-boundary failures: 6 passed.

## Notes

- No production-code change was required: the existing lazy Typer decoration and registered M145 service errors already route failures through the central boundary.
- The code review found no blocking issues for `P05.S26`.
