---
tags:
  - '#exec'
  - '#tui-registry-api-gate'
date: '2026-09-23'
modified: '2026-09-30'
body_schema: 'body-v2'
body_hash: 'sha256:71f2bea6613c7bafaed8c7fa3ba51177c7e168609349b34287f83e89231ace37'
related:
  - "[[2026-09-23-tui-registry-api-gate-plan]]"
---

# `tui-registry-api-gate` ledger

## Changes

- `S01` `M` `src/cadrumo/application/modelo/work_review.py`
- `S01` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_modelo_work_review.py`
- `S01` `verify:` `pytest-work-review` -> `pass`
- `S01` `verify:` `ruff` -> `pass`
- `S01` `verify:` `ty` -> `pass`
- `S03` `M` `src/cadrumo/application/modelo/workspace_producers.py`
- `S03` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_modelo_work_review.py`
- `S03` `verify:` `pytest-work-review` -> `pass`
- `S03` `verify:` `pytest-workspace-producers` -> `pass`
- `S03` `verify:` `ruff` -> `pass`
- `S03` `verify:` `ty` -> `pass`
- `S04` `M` `src/cadrumo/application/modelo/workspace.py`
- `S04` `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `S04` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_modelo_work_review.py`
- `S04` `verify:` `pytest-work-review` -> `pass`
- `S04` `verify:` `pytest-tui-modelo-and-workbench` -> `pass`
- `S04` `verify:` `pytest-modelo-workspace` -> `pass`
- `S04` `verify:` `ruff` -> `pass`
- `S04` `verify:` `ty` -> `pass`
- `S05` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_modelo_workspace_destinations.py`
- `S05` `verify:` `pytest-projection-reader` -> `pass`
- `S05` `verify:` `pytest-installed-workspace` -> `pass`
- `S05` `verify:` `pytest-destinations-neighbour-refusal` -> `pass`
- `S07` `M` `src/cadrumo/domain/modelos/calculation_revision.py`
- `S07` `M` `src/cadrumo/application/modelo/calculation_resolution.py`
- `S07` `M` `src/cadrumo/application/modelo/_work_review_assembly.py`
- `S07` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_modelo_work_review.py`
- `S07` `verify:` `pytest-work-review` -> `pass`
- `S07` `verify:` `pytest-calculation-replay-and-boolean-channel` -> `pass`
- `S07` `verify:` `harness-modelo-100-scenario` -> `pass`
- `S07` `verify:` `ruff` -> `pass`
- `S07` `verify:` `ty` -> `pass`
- `S02` `M` `src/cadrumo/adapters/persistence/profile/tests/test_workspace.py`
- `S02` `M` `src/cadrumo/application/modelo/calculation.py`
- `S02` `M` `src/cadrumo/application/modelo/work_addressing.py`
- `S02` `M` `src/cadrumo/application/modelo/workspace.py`
- `S02` `M` `src/cadrumo/application/modelo/workspace_manifest.py`
- `S02` `M` `src/cadrumo/application/modelo/workspace_producers.py`
- `S02` `M` `src/cadrumo/application/state_projection.py`
- `S02` `M` `src/cadrumo/application/tests/test_workbench_generation.py`
- `S02` `M` `src/cadrumo/core/i18n/locale_catalogue.py`
- `S02` `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `S02` `M` `src/cadrumo/entrypoints/tui/modelo/view/tests/test_export_result_lifecycle.py`
- `S02` `M` `src/cadrumo/entrypoints/tui/modelo/view/tests/test_modelo_projection_reader.py`
- `S02` `verify:` `pytest-workspace-admission-module` -> `pass`
- `S02` `verify:` `pytest-s02-wide-1952` -> `pass`
- `S02` `verify:` `ruff` -> `pass`
- `S02` `verify:` `ty-linux-win32` -> `pass`
- `S06` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_modelo_workspace_destinations.py`
- `S06` `verify:` `pytest-destinations` -> `pass`
- `S06` `verify:` `scenario-render-336-captures` -> `pass`
- `S06` `verify:` `results-refusing-0-of-48` -> `pass`
- `S06` `verify:` `verification-unmeasured-0-of-48` -> `pass`

## Notes

- `S02` Wide run: one failure, `test_exception_base_hygiene,` names exception classes in `value_presentation.py,` `source_policy.py` and `work_form.py,` which a concurrent session committed or holds untracked; not touched here. The schema-record determinism test in `test_workspace.py` failed once in a full-module run and passed in nine subsequent runs.
- `S06` The acceptance render captured all 336 scenario frames with no crash or golden divergence, but refused to write its manifest because a concurrent session committed TUI source (fa69c192fb, 6f72ccb9f8) during the run; acceptance was read from the captured text of every Results, Verification and Inputs page.
