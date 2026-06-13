---
tags: ['#exec', '#modelo-work-revision-cli-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S05'
related:
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-plan]]'
---

# W01.P02.S05 Execution

Focused verification completed for the revision read extraction.

Passed:
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_work_revision_cli.py src/aeat/entrypoints/cli/test_modelo_work_ux.py src/aeat/entrypoints/cli/test_modelo_work_natural_key.py src/aeat/entrypoints/cli/test_architecture_boundaries.py src/aeat/entrypoints/cli/test_cli_module_size.py`
- `uv run --no-sync python -m compileall -q src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_work_revision_cli.py`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo_work_ux.py::test_work_revisions_accepts_a_positional_work_unit_id src/aeat/entrypoints/cli/test_modelo_work_ux.py::test_work_revisions_resolves_a_visible_filing_target src/aeat/entrypoints/cli/test_modelo_work_ux.py::test_work_revision_shows_persisted_casilla_values src/aeat/entrypoints/cli/test_modelo_work_ux.py::test_work_revision_rejects_an_unknown_revision_id -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_architecture_boundaries.py -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_cli_module_size.py::test_cli_command_functions_do_not_grow_past_complexity_budget -q`

Residual:
- The broad module-size guard still reports unrelated existing over-budget modules `_app_live.py` and `_ledger.py`; this slice did not modify those files.
