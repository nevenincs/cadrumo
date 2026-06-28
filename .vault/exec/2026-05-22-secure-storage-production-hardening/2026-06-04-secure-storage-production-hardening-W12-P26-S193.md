---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S193'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s193-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S193`

Closed `AFR-091` for the source-mesh aggregation contract module.

## Description

- Reviewed `src/aeat/application/aggregation/_source_mesh.py` against the
  `manifest-discovery` manifest-bucket classification.
- Verified the module remains a pure source-resolution contract surface, with no
  repository construction, settings access, environment access, or storage-route
  ownership.
- Localized `SourceMeshError` field-validator failures for owned source and
  source transaction id invariants, adding locale strings through
  `python -m aeat.locales set`.
- Updated the Renta source-mesh ledger test fixture to inject a bucket-bound
  `InvoiceCatalogueRepository`, matching the S192 invoice repository contract.
- Validated source-mesh merge, degradation, ledger, and profile source coverage.

## Outcome

`AFR-091` is closed as a source-mesh boundary closure slice. The source mesh
continues to carry bucket scope as typed context and diagnostics, while concrete
storage access remains in repository-backed resolvers. Validator failures now
also participate in the project locale-message convention.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/aggregation/_source_mesh.py src/aeat/application/aggregation/test_source_mesh.py src/aeat/application/aggregation/test_modelo_source_mesh_ledger.py src/aeat/application/aggregation/test_source_mesh_profile_live.py`
- `uv run --no-sync pytest -q src/aeat/application/aggregation/test_source_mesh.py src/aeat/application/aggregation/test_modelo_source_mesh_ledger.py src/aeat/application/aggregation/test_source_mesh_profile_live.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No pragma/noqa suppressions, monkeypatches, fakes, or naked environment access
were added.
