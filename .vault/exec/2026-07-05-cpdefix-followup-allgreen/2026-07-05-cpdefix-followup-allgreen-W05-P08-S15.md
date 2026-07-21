---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S15'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---
# Verify relocated regularizacion source-mesh enrollment gates after the no-reexport cleanup

## Scope

- `src/aeat/application/modelo/tests/test_bienes_inversion_regularizacion_source_mesh_enrollment.py`
- `src/aeat/application/modelo/tests/test_prorrata_regularizacion_source_mesh_enrollment.py`

## Description

- Re-ran RAG/code discovery for residual cpdefix source-mesh and official-surface blockers.
- Confirmed the regularizacion enrollment tests now live under `src/aeat/application/modelo/tests` while the older `src/aeat/application/aggregation/tests` paths are deleted by concurrent worktree changes.
- Verified the relocated tests after the no-reexport import cleanup.

## Outcome

The focused relocated enrollment gate is green:

- `uv run --no-sync ruff check src/aeat/application/modelo/tests/test_bienes_inversion_regularizacion_source_mesh_enrollment.py src/aeat/application/modelo/tests/test_prorrata_regularizacion_source_mesh_enrollment.py` - passed.
- `uv run --no-sync pytest -q src/aeat/application/modelo/tests/test_bienes_inversion_regularizacion_source_mesh_enrollment.py src/aeat/application/modelo/tests/test_prorrata_regularizacion_source_mesh_enrollment.py -n 0` - `3 passed`.

## Notes

The shared worktree still contains many unrelated dirty files and concurrent relocated-path deletes. The verification step intentionally did not stage or commit those broader changes.
