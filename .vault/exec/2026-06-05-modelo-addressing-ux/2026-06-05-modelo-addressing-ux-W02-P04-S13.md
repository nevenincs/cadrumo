---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S13'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W02.P04.S13 - readiness command registrar

Scope: extract modelo readiness command registration into a focused module.

## Description

- Add `src/aeat/entrypoints/cli/_modelo_readiness_cli.py`.
- Move the `modelo readiness` command out of `_modelo.py`.
- Preserve the existing command signature and output contract.
- Remove duplicated readiness line assembly from the legacy root.
- Fix backend registry revision validation so unknown revisions become domain/user-input errors instead of `KeyError`.
- Tighten the `_modelo.py` frozen size budget from 3735 to 3576 lines after extraction.

## Outcome

`modelo readiness` is now registered from `_modelo_readiness_cli.py`, and `_modelo.py` mounts it through `register_readiness_commands`. The backend addressing facade now names unknown registry revision IDs cleanly.

## Notes

Verification commands passed:

- `uv run --no-sync ruff check` over touched CLI and application files.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo.py::test_work_create_rejects_unknown_modelo src/aeat/entrypoints/cli/test_modelo.py::test_work_create_rejects_unknown_revision src/aeat/entrypoints/cli/test_modelo_work_natural_key.py::test_work_create_refuses_conflicting_registry_revision_for_visible_target -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo_discovery_defects.py src/aeat/entrypoints/cli/test_modelo_work_natural_key.py src/aeat/entrypoints/cli/test_modelo_work_ux.py -q`
