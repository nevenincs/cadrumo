---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S24'
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
     The S24 and 2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan placeholders are machine-filled by
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
     The Keep Modelo 145 argument parsing separate from business behavior and ## Scope

- `src/aeat/entrypoints/cli` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Keep Modelo 145 argument parsing separate from business behavior

## Scope

- `src/aeat/entrypoints/cli`

## Description

- Ground `P05.S24` from the current plan status, the reopening ADR/research, semantic search for the M145 CLI boundary, and the existing workflow-run CLI analogue.
- Extract Modelo 145 CLI token normalization into `_modelo_m145_parsing.py` so actor fallback, repeated `--casilla` parsing, and create-command DTO construction stay outside the command callbacks.
- Keep `m145` command callbacks thin: resolve the active bucket, call parser helpers, delegate communication create/export/transition/validation to the backend service, and emit the existing command payloads.
- Add parser-boundary tests for create-command construction, required `--casilla` refusal, supplied actor trimming, and real default-actor fallback.
- Re-run the existing real M145 CLI integration flow to prove the parser refactor preserves end-to-end behavior.

## Outcome

- `P05.S24` implementation is complete and ready for plan-row closure.
- Verification passed:
  - Focused ruff check for the S24 parser, CLI registration, and tests: passed.
  - Focused ruff format check for the S24 parser, CLI registration, and tests: passed.
  - M145 parser-boundary unit slice: 4 passed.
  - M145 real CLI integration slice: 4 passed.

## Notes

- No filing, deadline, live-read, portal, submit, receipt, shim, stub, fake-support, or compatibility-alias surface was added.
- Backend validation, export, persistence, events, and state transitions remain owned by the Modelo 145 communication service.
