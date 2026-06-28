---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S24'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W03.P06.S24 calculate boundary exact and semantic audits

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py`
- `src/aeat/entrypoints/cli/_modelo_cli_support.py`
- `src/aeat/application/modelo/_calculate_input.py`

## Description

- Ran exact `rg` audit for calculate business-policy terms across CLI calculate modules and `_calculate_input.py`.
- Ran exact `rg` audit for private `domain.modelos._*` imports in the touched production CLI files.
- Ran semantic `vaultspec-rag` code searches for calculate command business-logic boundary and transport parsing versus application shortcut ownership.
- Ran semantic `vaultspec-rag` vault search for the calculate registrar/support extraction records.
- Tightened the architecture guard so `_modelo.py` has a zero private-domain import budget.

## Outcome

The audit supports the intended boundary. CLI calculate modules contain command registration, rendering, token parsing, and delegation. Application code owns `build_work_calculate_input_bundle`, `calculate_modelo_work_revision`, casilla normalization, non-numeric casilla refusal, row aggregate validation, binding split, relation coercion, and shortcut application. The touched production CLI files no longer import private `domain.modelos._*` modules.

## Verification

- Exact audit found `calculate_modelo_work_revision` only delegated from `_modelo_work_calculate_cli.py` and implemented in `_calculate_input.py`.
- Exact audit found `build_work_calculate_input_bundle` delegated from `_modelo_cli_support.py` and implemented in `_calculate_input.py`.
- `uv run --no-sync vaultspec-rag search "modelo work calculate CLI business logic boundary build_work_calculate_input_bundle" --type code --port 8766 --max-results 8 --json` returned `_modelo.py` import wiring, `_calculate_input.py` `build_work_calculate_input_bundle`, `_calculate_input.py` `calculate_modelo_work_revision`, and `_modelo_work_calculate_cli.py` command registration among top results.
- `uv run --no-sync vaultspec-rag search "calculate transport parsing helpers casilla binding row shortcut application application layer" --type code --port 8766 --max-results 8 --json` returned `_calculate_input.py` `apply_calculation_shortcut_inputs`, `_modelo_cli_support.py` raw Typer option parsing, and `_calculate_input.py` shortcut ownership docstring among top results.
- `uv run --no-sync vaultspec-rag search "work calculate command registrar transport parsing no business policy" --type vault --feature modelo-addressing-ux --port 8766 --max-results 8 --json` returned the S17-S20 execution records.
- `rg -n "from \.\.\.domain\.modelos\._|domain\.modelos\._" src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_cli_support.py src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py` returned no matches.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_architecture_boundaries.py -q` passed with 5 tests.
