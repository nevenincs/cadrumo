---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S85'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-production-hardening-W12-P21-S84]]'
  - '[[2026-05-26-secure-storage-production-hardening-w12-p21-s85-review-audit]]'
---



# `secure-storage-production-hardening` `W12.P21.S85`

Migrated application-layer secure-object defaults to active-profile runtime resolution and removed deprecated storage setup from the intersecting tests.

## Changes

- Added an adapter-owned active-bucket repository factory so application code can resolve the active profile without reimplementing pointer logic.
- Routed auth diagnostics, borrador Modelo 100 snapshots, modelo reconciliation catalogue writes, application diagnostics, and repair-integrity default paths through runtime-owned secure-object repositories.
- Kept explicit repository injection for tests and call sites that already own a real secure-object repository.
- Migrated S85-focused tests away from `AEAT_DATABASE_URL` and monkeypatch-based storage setup to `override_settings` with `aeat_local_storage_root`, `aeat_active_profile`, and real `EphemeralMasterKeyProvider` sessions.
- Narrowed diagnostic and repair-integrity exception handling to typed AEAT, storage, SQLAlchemy, validation, and OS failure classes instead of broad `Exception` catches.
- Promoted the modelo work-unit namespace to a public repository constant and consumed that constant from repair integrity, removing the parallel namespace literal from the application layer.

## Validation

- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/runtime_repository.py src/aeat/adapters/persistence/storage/envelope/_secure_repository.py src/aeat/application/auth/_diagnostics.py src/aeat/application/live/_borrador_100.py src/aeat/application/modelo/_reconcile.py src/aeat/application/repair_integrity.py src/aeat/application/diagnostics.py src/aeat/domain/modelos/_repository.py src/aeat/application/auth/test_diagnostics.py src/aeat/application/live/test_borrador_100.py src/aeat/application/live/test_borrador_100_roundtrip.py src/aeat/application/modelo/test_reconcile.py src/aeat/application/test_repair_integrity.py src/aeat/application/test_diagnostics.py src/aeat/domain/modelos/test_work_unit.py`
- `uv run --no-sync pytest src/aeat/application/auth/test_diagnostics.py src/aeat/application/live/test_borrador_100.py src/aeat/application/live/test_borrador_100_roundtrip.py src/aeat/application/modelo/test_reconcile.py src/aeat/application/test_repair_integrity.py src/aeat/application/test_diagnostics.py src/aeat/domain/modelos/test_work_unit.py::test_no_parallel_work_unit_storage_namespace -q`
- `rg -n "SecureObjectRepository\(|objects or SecureObjectRepository|SecureBoundRepository\(|AEAT_DATABASE_URL|monkeypatch|except Exception|pragma|noqa|aeat\.domain\.modelos\.work_units" ...`

## Notes

- The production scan found no remaining raw secure-object constructor defaults in the targeted S85 production files.
- Direct `SecureObjectRepository(engine=...)` calls remain only in real-behavior tests that intentionally seed or mutate a concrete SQL database under a real master-key provider.
- The remaining `noqa: S603` in diagnostics is limited to a fixed trusted local `uv` subprocess invocation and is not part of the secure-storage repository path.
