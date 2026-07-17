---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-04'
modified: '2026-07-17'
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
- Reconcile the verification record after the concurrent DR145 fixed-width layout completion.

## Outcome

- `uv run --no-sync pytest -q -n 0 src/aeat/domain/calculations/registry/tests/test_modelo_145_source_catalogue.py src/aeat/domain/calculations/registry/tests/test_modelo_145_registry_foundation.py src/aeat/domain/calculations/registry/tests/test_source_enrollment.py src/aeat/domain/calculations/registry/tests/test_support_matrix.py --tb=short` passed with 23 tests.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/tests/test_modelo_145_registry_foundation.py` passed.
- A direct authority/support-matrix probe reported 50 Modelo 145 casillas, parity `modelo-145-dr-v20`, one export layout `modelo-145-dr-v20-fixed-width`, one `communication` record with 53 fields, 50 casillas carrying `export_refs`, and `has_fixed_width_export=True`.

## Notes

- The first review caught a missing-registry integration failure after the marker-only export layout correction. The registry foundation was restored and re-reviewed successfully.
- A later no-export correction was overtaken by concurrent completion of the DR145 fixed-width layout. The current verified state keeps the layout and matching casilla `export_refs`.
- `P03.S13` is closed for registry metadata. Backend-owned export behavior remains scheduled under `P04.S19`.
