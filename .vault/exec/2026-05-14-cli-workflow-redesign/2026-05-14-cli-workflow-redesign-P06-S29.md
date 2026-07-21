---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-08'
step_id: 'S29'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

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
