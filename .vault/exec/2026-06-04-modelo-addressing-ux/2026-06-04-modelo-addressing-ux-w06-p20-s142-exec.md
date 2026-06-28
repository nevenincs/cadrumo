---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S142'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P20.S142 Modelo CLI support helper extraction

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/_modelo_cli_support.py`
- `src/aeat/entrypoints/cli/_modelo_rendering.py`
- `src/aeat/entrypoints/cli/_modelo_work_runs_cli.py`
- `src/aeat/entrypoints/cli/_modelo_maritime_cli.py`
- `src/aeat/application/modelo/_maritime_preview.py`

## Description

- Move modelo work rendering and payload projection helpers out of the monolithic CLI module into `_modelo_rendering.py`.
- Keep `_modelo.py` consuming shared support helpers from `_modelo_cli_support.py` instead of owning ID-shape validation, selector refusal rendering, revision selector parsing, and default actor resolution.
- Move maritime active-profile fact resolution and RETMAR retry policy into the application-layer `preview_maritime_exemption_for_active_profile` service.
- Move workflow run discovery and resume commands into `_modelo_work_runs_cli.py`, with dependencies passed in from `_modelo.py` so extracted modules do not import the legacy root.
- Preserve the public command names and output payload shapes for `work preview-maritime-exemption`, `work runs`, and `work resume`.

## Outcome

- `_modelo.py` no longer owns the rendering helpers for work units, calculation revisions, filing records, verification reports, or result summaries.
- `_modelo.py` no longer owns the workflow-run command bodies.
- The maritime CLI body now delegates business workflow decisions to `aeat.application.modelo`.
- Focused support modules are available for later work command extraction without circular imports into `_modelo.py`.

## Notes

- The remaining work-create/calculate/verify/file command bodies are still in `_modelo.py`; W06.P20 continues through further command-group extraction steps.
- `RentaValidationError` remains an explicit CLI exception catch for the maritime input-validation boundary so DA41 refusal still propagates through the registered AeatError path.

Verification:
- `.venv\Scripts\python.exe -m py_compile src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_cli_support.py src/aeat/entrypoints/cli/_modelo_work_runs_cli.py src/aeat/entrypoints/cli/_modelo_rendering.py src/aeat/entrypoints/cli/test_architecture_boundaries.py src/aeat/entrypoints/cli/test_cli_module_size.py` - passed.
- `.venv\Scripts\ruff.exe check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_cli_support.py src/aeat/entrypoints/cli/_modelo_work_runs_cli.py src/aeat/entrypoints/cli/_modelo_rendering.py src/aeat/entrypoints/cli/test_architecture_boundaries.py src/aeat/entrypoints/cli/test_cli_module_size.py --select F401,F821,E501,F811` - passed.
- `.venv\Scripts\pytest.exe src/aeat/entrypoints/cli/test_work_resume.py src/aeat/entrypoints/cli/test_modelo_work_preview_maritime_exemption.py src/aeat/entrypoints/cli/test_modelo_work_natural_key.py -q` - 20 passed.
