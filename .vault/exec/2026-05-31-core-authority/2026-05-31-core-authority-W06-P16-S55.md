---
step_id: S55
date: 2026-05-31
modified: '2026-05-31'
tags:
  - "#exec"
  - "#core-authority"
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W06.P16.S55

## Summary

Extracted repository Protocol interfaces for all remaining domain aggregate `_repository.py` files and moved adapter-layer imports behind `TYPE_CHECKING` guards or deferred local imports.

## Changes

**New files:**
- `src/aeat/domain/fincas/_protocols.py` — 5 Protocols: `FincaRepositoryProtocol`, `ArrendamientoRepositoryProtocol`, `FincaRendimientoRepositoryProtocol`, `FincaGastoRepositoryProtocol`, `FincaAmortizacionLedgerRepositoryProtocol`
- `src/aeat/domain/justificante/_protocols.py` — `JustificanteRepositoryProtocol`

**Extended files:**
- `src/aeat/domain/filing/_protocols.py` — added `ModeloDraftRepositoryProtocol`
- `src/aeat/domain/submission/_protocols.py` — added `SubmissionRepositoryProtocol`

**Adapter import deferrals:**
- `submission/_repository.py`: `ClassificationError`/`EnvelopeVersionError` to deferred local import in `iter_submissions()`; removed from `__all__`
- `submission/_engine.py`: `StorageError` deferred into `load_submission()`
- `filing/_repository.py`: error types and `SecureObjectRepository` to `TYPE_CHECKING`
- `filing/_complementaria_repository.py`: all adapter imports deferred to method bodies
- `filing/_runtime_repository.py`: `runtime_repository` and `SecureObjectRepository` deferred
- `justificante/_repository.py`: error types to `TYPE_CHECKING`
- `modelos/_runtime_repository.py`: both adapter imports deferred
- `usage_ratios/_service.py`: all four module-scope adapter imports deferred to function bodies

## Constraint Notes

Three `_repository.py` files retain module-scope adapter imports (`SensitivityClass` + `SecureBoundRepository`) due to the base-class inheritance constraint — the concrete class inherits `SecureBoundRepository[T]` and assigns `SensitivityClass.X` as a `ClassVar` value. Eliminating these requires relocating the concrete class to the adapter layer, deferred to a later wave.

Affected files: `submission/_repository.py`, `filing/_repository.py`, `justificante/_repository.py`.

## Test Results

420 passed across all affected packages (submission, filing, justificante, fincas, modelos, usage_ratios). One pre-existing failure: `justificante/test_repository.py::TestClassificationGate::test_foreign_class_object_refused` (same pattern as pre-existing `submission` test failure, predates W06).

## Commit

`f9203ef8b` — feat(domain): W06.P16.S55 - extract repository Protocols for remaining domain aggregates
