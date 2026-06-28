---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S12'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W02.P03.S12 - lifecycle natural-key regressions

Scope: cover lifecycle extraction with real natural-key CLI regressions.

## Description

- Run natural-key modelo work tests over the extracted lifecycle command registration.
- Run modelo work UX tests over the extracted lifecycle command registration.
- Run static architecture and module-size guards over the new module and legacy root.
- Compile the touched CLI modules.

## Outcome

The extracted lifecycle surface preserves the existing natural-key behavior and operator-facing UX. Focused verification passed with 29 tests.

## Notes

Verification commands passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_work_lifecycle_cli.py src/aeat/entrypoints/cli/_modelo_rendering.py src/aeat/entrypoints/cli/test_architecture_boundaries.py src/aeat/entrypoints/cli/test_cli_module_size.py`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_architecture_boundaries.py src/aeat/entrypoints/cli/test_cli_module_size.py src/aeat/entrypoints/cli/test_modelo_work_natural_key.py src/aeat/entrypoints/cli/test_modelo_work_ux.py -q`
