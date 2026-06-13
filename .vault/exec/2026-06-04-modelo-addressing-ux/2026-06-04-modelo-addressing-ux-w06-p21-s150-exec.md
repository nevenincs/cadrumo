---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S150'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P21.S150 Static CLI boundary gates

Scope:
- `src/aeat/entrypoints/cli/test_architecture_boundaries.py`
- `src/aeat/entrypoints/cli/test_cli_module_size.py`

## Description

- Run static architecture guard for extracted modelo CLI modules.
- Run static CLI module size guard.
- Run static CLI command/registrar size guard.
- Run targeted Ruff over changed CLI and application files.

## Outcome

- Extracted modelo CLI modules do not import the monolithic `_modelo.py` root.
- Extracted modelo CLI modules do not import private application modules.
- Untracked private-domain imports in extracted modelo CLI modules are refused by test.
- CLI module and command size budgets pass.
- Targeted Ruff passes on changed modelo CLI modules, support/rendering modules, and static guard tests.

## Notes

- Known legacy monolith line budgets are intentionally frozen rather than treated as healthy.

Verification:
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_architecture_boundaries.py src/aeat/entrypoints/cli/test_cli_module_size.py -q` - 5 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_architecture_boundaries.py src/aeat/entrypoints/cli/test_cli_module_size.py src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_cli_support.py src/aeat/entrypoints/cli/_modelo_rendering.py src/aeat/entrypoints/cli/_modelo_export_cli.py src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py src/aeat/entrypoints/cli/_modelo_m036_cli.py src/aeat/entrypoints/cli/_modelo_maritime_cli.py src/aeat/entrypoints/cli/_modelo_projection_cli.py src/aeat/entrypoints/cli/_modelo_work_runs_cli.py` - passed.
