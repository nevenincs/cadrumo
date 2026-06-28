---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S35'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W05.P09.S35 architecture and semantic gates

Scope:
- `src/aeat/entrypoints/cli`
- `src/aeat/application/modelo`

## Description

- Ran architecture boundary tests after W03 calculate extraction.
- Ran command complexity guard after W03 calculate extraction.
- Ran exact `rg` audits for private domain imports and calculate boundary terms.
- Ran semantic `vaultspec-rag` audits for calculate registrar extraction, support parsing, and application facade ownership.
- Lowered `_modelo.py` module budget to the measured post-extraction size.

## Outcome

The touched modelo CLI surface passes architecture and command complexity gates. `_modelo.py` now has zero allowed private-domain import budget, and the touched production CLI files have no private `domain.modelos._*` imports.

## Verification

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_architecture_boundaries.py src/aeat/entrypoints/cli/test_cli_module_size.py::test_cli_command_functions_do_not_grow_past_complexity_budget -q` passed with 6 tests.
- `rg -n "from \.\.\.domain\.modelos\._|domain\.modelos\._" src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_cli_support.py src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py` returned no matches.
- `uv run --no-sync vaultspec-rag server service status` reported the RAG service healthy and ready.
- `uv run --no-sync vaultspec-rag search "modelo work calculate CLI support parser application calculate input bundle no business logic" --type code --language python --max-results 12 --port 8766 --json` returned `_modelo.py`, `_calculate_input.py`, and `_modelo_work_calculate_cli.py` as relevant surfaces.
- `uv run --no-sync vaultspec-rag search "work calculate command registrar transport parsing no business policy application facade" --type code --language python --max-results 12 --port 8766 --json` returned `_modelo_work_calculate_cli.py` registrar and command surfaces.

## Notes

- Broad `test_cli_module_size.py::test_production_cli_modules_do_not_grow_into_new_monoliths` still fails only on unrelated `_app_live.py`, which has 2262 lines against its existing 2117-line budget.
