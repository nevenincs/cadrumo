---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S15'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

# Verify Modelo 145 registry load, source grounding, export metadata, and rejected filing surfaces

## Scope

- `tests/domain/calculations/registry`

## Description

- Add focused Modelo 145 registry foundation coverage for authority loading, source grounding, non-filing surfaces, parity metadata, and export-support honesty.
- Re-run source-catalogue, Modelo 145 foundation, source-enrollment, and support-matrix gates.
- Run a formal code-review pass after the initial export-layout overclaim was removed.

## Outcome

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/tests/test_modelo_145_source_catalogue.py src/aeat/domain/calculations/registry/tests/test_modelo_145_registry_foundation.py src/aeat/domain/calculations/registry/tests/test_source_enrollment.py src/aeat/domain/calculations/registry/tests/test_support_matrix.py --tb=short` passed with 22 tests.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/tests/test_modelo_145_registry_foundation.py` passed.
- A direct authority/support-matrix probe reported 14 Modelo 145 casillas, parity `modelo-145-dr-v20`, zero export layouts, and `has_fixed_width_export=False`.
- The code-reviewer found no active issue after the repaired state.

## Notes

- The first review caught a missing-registry integration failure after the marker-only export layout correction. The registry foundation was restored and re-reviewed successfully.
- `P03.S13` remains open because no complete fixed-width value-field export layout has been implemented.
