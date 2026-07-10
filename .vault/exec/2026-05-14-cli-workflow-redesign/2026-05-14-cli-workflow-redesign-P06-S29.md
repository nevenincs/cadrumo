---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S29'
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
     The S29 and 2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan placeholders are machine-filled by
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
     The Add CLI behavior tests exercising Modelo 145 through real backend services and ## Scope

- `tests/entrypoints/cli` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add CLI behavior tests exercising Modelo 145 through real backend services

## Scope

- `tests/entrypoints/cli`

## Description

Harden the Modelo 145 CLI lifecycle integration test so it observes the real persisted backend state after CLI-driven completion.

Return the isolated runtime bucket id from the CLI backend fixture and use the application read service to verify the record is stored as locally completed.

Keep the CLI path as the behavior under test: create, validate, export, delivered-to-payer, and locally completed commands still run through the Typer entrypoint.

## Outcome

`src/aeat/entrypoints/cli/tests/test_m145_communication_cli.py` now proves that the CLI lifecycle command sequence persists the final Modelo 145 communication record state in the real backend service, not only in the rendered CLI payload.

Verification:

- `uv run --no-sync ruff format --check src\aeat\entrypoints\cli\tests\test_m145_communication_cli.py`
- `uv run --no-sync ruff check src\aeat\entrypoints\cli\tests\test_m145_communication_cli.py`
- `uv run --no-sync pytest src\aeat\entrypoints\cli\tests\test_m145_communication_cli.py -m integration -q`

## Notes

No blockers. The unmarked pytest invocation intentionally collected no tests because the file is marked `integration`; the step gate was run with `-m integration`.
