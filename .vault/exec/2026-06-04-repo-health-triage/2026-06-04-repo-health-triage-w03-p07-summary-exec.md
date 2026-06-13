---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W03.P07` summary

The modelo CLI extraction wave began with a low-risk split of the `modelo work` Typer construction and the `work calculate` input preparation boundary.

- Modified: `src/aeat/entrypoints/cli/_modelo.py`
- Modified: `src/aeat/entrypoints/cli/test_modelo_work_ux.py`
- Created: `src/aeat/entrypoints/cli/_modelo_work.py`
- Created: `src/aeat/application/modelo/_calculate_input.py`

## Description

The slice isolates the `modelo work` Typer app construction, introduces a typed input bundle for calculation inputs, preserves command registration compatibility, and corrects the in-process modelo-work UX fixture so it follows the same active UUID bucket session path as real CLI invocations.

Verification completed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_work.py src/aeat/application/modelo/_calculate_input.py src/aeat/entrypoints/cli/test_modelo_work_ux.py`
- `uv run --no-sync ty check src/aeat/entrypoints/cli/_modelo_work.py src/aeat/application/modelo/_calculate_input.py --output-format concise`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo.py::test_work_calculate_binding_help_points_at_bindings_list src/aeat/entrypoints/cli/test_modelo.py::test_work_calculate_enters_bucket_source_mesh_calculation_boundary src/aeat/entrypoints/cli/test_modelo_work_ux.py::test_work_calculate_confirms_the_draft_was_saved -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo_work_ux.py -q`

Whole-file `_modelo.py` Pyright and `ty` remain blocked by existing monolith baseline diagnostics and are not promoted as this slice's pass/fail gate.
