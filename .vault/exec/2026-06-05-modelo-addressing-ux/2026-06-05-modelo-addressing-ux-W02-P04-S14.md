---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S14'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W02.P04.S14 - discovery command extraction

Scope: extract bindings, casillas, formulas, and registry discovery command registration into a focused CLI module.

## Description

- Add `src/aeat/entrypoints/cli/_modelo_discovery_cli.py`.
- Move `modelo list`, `modelo describe`, `modelo casillas`, `modelo formulas`, `modelo bindings list`, and `modelo bindings preview` command registration out of `_modelo.py`.
- Preserve existing command signatures, payload construction, text rendering, period normalization, binding override parsing, and bad-parameter translation.
- Mount the extracted command registrar from `_modelo.py` after the shared CLI parsing helpers are defined.
- Tighten the `_modelo.py` frozen size budget from 3576 to 3083 lines after extraction.

## Outcome

The registry discovery and binding-inspection surface is now registered from `_modelo_discovery_cli.py`, and `_modelo.py` delegates through `register_discovery_commands`. The legacy root no longer owns those command bodies.

## Notes

Verification commands passed:

- `uv run --no-sync ruff check` over touched CLI and application files.
- `uv run --no-sync python -m compileall -q src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_discovery_cli.py src/aeat/application/modelo/_registry_discovery.py`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo_discovery_defects.py src/aeat/entrypoints/cli/test_modelo.py::test_bindings_list_emits_readiness_category_for_every_row src/aeat/entrypoints/cli/test_bindings_list_missing_filter.py -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_architecture_boundaries.py -q`

The full CLI size guard still reports unrelated `_app_live.py` drift: `_app_live.py: 2135 lines > budget 2117`.
