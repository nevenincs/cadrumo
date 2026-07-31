---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:b132616179dc246d011e8fef75323eaece859de6af2552d63856e55af2098648'
step_id: 'S17'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---
# Replace bienes-inversion test-export repository imports with the real persistence adapter source

## Scope

- `src/aeat/application/calculations/tests/test_bienes_inversion_regularizacion.py`
- `src/aeat/application/modelo/tests/test_bienes_inversion_advisory.py`

## Description

- Grounded the no-reexport cleanup with `uvx vaultspec-rag search "test application_adapter_exports reexport real repository import no reexports tests provision from real sources" --type code`.
- Confirmed `BienesInversionIvaRegisterRepository` is defined in the real adapter module `src/aeat/adapters/persistence/profile/bienes_inversion.py`.
- Replaced the remaining tracked bienes-inversion test imports from `src/aeat/tests/application_adapter_exports.py` with direct imports from the real adapter source.

## Outcome

The capital-goods IVA regularizacion tests now provision `BienesInversionIvaRegisterRepository` from the concrete persistence adapter, not the test-export bundle. This matches the campaign no-reexport direction while preserving real encrypted repository behavior through `isolated_runtime_profile`.

Focused gates passed:

- `uv run --no-sync ruff check src/aeat/application/calculations/tests/test_bienes_inversion_regularizacion.py src/aeat/application/modelo/tests/test_bienes_inversion_advisory.py src/aeat/application/modelo/tests/test_bienes_inversion_regularizacion_source_mesh_enrollment.py` - passed.
- `uv run --no-sync pytest -q src/aeat/application/calculations/tests/test_bienes_inversion_regularizacion.py src/aeat/application/modelo/tests/test_bienes_inversion_advisory.py src/aeat/application/modelo/tests/test_bienes_inversion_regularizacion_source_mesh_enrollment.py -n 0` - `21 passed`.

## Notes

The relocated source-mesh enrollment test remains untracked in the shared worktree and was included only as a verification target, not as an owned source edit for this step.
