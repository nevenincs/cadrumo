---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S359'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S359 - Close AFR-257 for modelo work-unit model

Scope: close `AFR-257` for `src/aeat/domain/modelos/_work_unit.py` with signal
`manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`.

## Description

- Audited `_work_unit.py` for secure-storage, active-profile, manifest, settings,
  environment, filesystem, and runtime repository ownership.
- Confirmed the module defines typed value surfaces only: `WorkUnitState`,
  `derive_work_unit_id`, `WorkUnit`, and `WorkUnitCatalogue`.
- Confirmed it does not instantiate `SecureObjectRepository`, does not call runtime
  repository factories, does not read or write files, and does not resolve active
  profile settings.
- Confirmed persistence for this model is owned by
  `src/aeat/domain/modelos/_repository.py`, already closed under `W12.P26.S356`.
- Closed `W12.P26.S359` through `vaultspec-core vault plan step check` and updated
  the `AFR-257` register status to `closed`.

## Outcome

`AFR-257` is closed as `manifest-discovery`. The model remains a deterministic,
bucket-scoped value contract and does not own secure-storage routing or physical
persistence.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/modelos/_work_unit.py src/aeat/domain/modelos/test_work_unit_censo_stale.py src/aeat/domain/modelos/test_secure_storage_roundtrip.py`
- `uv run --no-sync pytest -q src/aeat/domain/modelos/test_work_unit_censo_stale.py src/aeat/domain/modelos/test_secure_storage_roundtrip.py`
- `uv run --no-sync pytest -q src/aeat/domain/modelos/test_repository_sensitivity_class.py`

## Notes

No production code changes were required. The existing type-checker ignore on the
custom catalogue iterator is scoped to the deliberate pydantic iteration override and
is not hiding secure-storage behavior.
