---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S16'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W02.P04.S16 - discovery extraction regression coverage

Scope: cover discovery extraction with CLI shape and readiness regressions.

## Description

- Run focused registry discovery defect tests after extraction.
- Run binding-list readiness and missing-filter CLI tests after extraction.
- Run natural-key modelo work UX tests to verify the adjacent work addressing flow still behaves correctly.
- Run static architecture boundary tests for CLI facade imports and registry authority access.
- Run the broad CLI size guard to confirm `_modelo.py` remains under its tightened budget and identify unrelated module-size drift.

## Outcome

The extracted discovery surface preserves the existing CLI output shape and readiness behavior. Natural-key work UX tests continue to pass, and the architecture boundary guard now enforces zero direct registry authority reads from the legacy root.

## Notes

Verification commands passed:

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo_discovery_defects.py src/aeat/entrypoints/cli/test_modelo.py::test_bindings_list_emits_readiness_category_for_every_row src/aeat/entrypoints/cli/test_bindings_list_missing_filter.py -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo_work_natural_key.py src/aeat/entrypoints/cli/test_modelo_work_ux.py -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_architecture_boundaries.py -q`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-05-modelo-addressing-ux-plan.md`

Known unrelated gate failure:

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_cli_module_size.py -q` fails only on `_app_live.py: 2135 lines > budget 2117`.

Plan check passes with the existing PLAN022 warning about non-monotonic document order.
