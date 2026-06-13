---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S17'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W03.P05.S17 calculate command registrar extraction

Scope:
- `src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py`
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

- Verified that `modelo work calculate` is registered by `register_work_calculate_commands` in the focused `_modelo_work_calculate_cli.py` module.
- Verified that the module owns the Typer command declaration, command options, result rendering, and calculate command execution wrapper.
- Confirmed `_modelo.py` imports the registrar and passes dependencies into it instead of defining the command body inline.

## Outcome

The calculate command registration extraction is present and operational. This step was implemented before this execution slice but had not been tracked in the successor plan, so this record closes the tracking gap.

## Verification

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_cli_support.py src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py src/aeat/entrypoints/cli/test_work_calculate_row_flag.py` passed.
- `uv run --no-sync python -c "from aeat.entrypoints.cli._modelo import app; from aeat.entrypoints.cli._modelo_cli_support import work_calculate_input_bundle_from_cli, parse_row_spec; print(app.info.name, work_calculate_input_bundle_from_cli.__name__, parse_row_spec.__name__)"` printed `modelo work_calculate_input_bundle_from_cli parse_row_spec`.

