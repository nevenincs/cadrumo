---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-production-hardening-W02-P04-S17]]'
---



# `secure-storage-production-hardening-W02-P04-S17` Code Review

S17-001 | LOW | Broad exception catch weakens the borrador anti-tautology proof
`src/aeat/application/live/test_borrador_100_roundtrip.py` catches `(ValidationError, Exception)` after mutating the persisted `superseded_by_snapshot_id` field. Because `Exception` subsumes unrelated storage/runtime failures, the test can pass for reasons other than the expected payload-validation failure or strict inequality. Narrow the accepted exception path to the concrete validation/decode failure expected from `repo.load(original.snapshot_id)`, or assert the loaded payload outcome directly.

S17-CHECK-001 | PASS | Production live secure-object construction is runtime-created
`src/aeat/application/live/_censo.py` now lazily resolves `CensoSnapshotRepository` through `secure_object_repository_for_bucket`, matching the existing `Borrador100SnapshotRepository` runtime-backed pattern in `src/aeat/application/live/_borrador_100.py`. The S17 touched files contain no production direct `SecureObjectRepository()` construction, no direct `get_engine()` default route, and no `AEAT_DATABASE_URL`/`aeat_database_url` shortcut.

S17-CHECK-002 | PASS | Runtime bucket route is exercised by touched live tests
`src/aeat/application/live/test_census_snapshot.py`, `src/aeat/application/live/test_borrador_100_roundtrip.py`, `src/aeat/application/live/test_iva_wallet_capture_backend.py`, and `src/aeat/application/live/test_filed_capture_calculation_history.py` use `override_settings(aeat_local_storage_root=...)` with active `BucketSession` contexts instead of naked environment mutation or monkeypatch-based storage routing. The wallet and filed-history coverage reaches the `SecureBoundRepository` default runtime path for calculation observations, IVA compensation history, and wallet decisions.

S17-CHECK-003 | PASS | Exception and i18n conventions remain aligned
The census repository keeps `AeatError`-derived lookup errors and uses existing storage-layer `ClassificationError` and `EnvelopeVersionError` contracts. Runtime readiness failures stay below the shared storage runtime boundary with translated-message keys; S17 did not introduce a new untranslated storage readiness path.

S17-CHECK-004 | PASS | Verification executed
`uv run ruff check src/aeat/application/live/_censo.py src/aeat/application/live/test_census_snapshot.py src/aeat/application/live/test_borrador_100_roundtrip.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/live/test_filed_capture_calculation_history.py` passed. `uv run pytest src/aeat/application/live/test_census_snapshot.py src/aeat/application/live/test_borrador_100_roundtrip.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/live/test_filed_capture_calculation_history.py -q` passed with 27 tests.

S17-RISK-001 | LOW | Deferred live JSONL snapshot stores remain out of S17 scope
The remaining live notification and expediente snapshot services still use the existing JSONL snapshot repository path. The S17 exec record identifies those plain-file stores as deferred to later live snapshot migration rows, so they are not counted as S17 failures but remain residual secure-storage migration risk.

## Resolution

S17-001 | RESOLVED | The borrador anti-tautology proof now accepts only the concrete validation path for the corrupted supersession payload: `ValidationError` or `LiveApplicationInputError` with a `superseded` message. It no longer catches broad `Exception`.

Resolution validation:

- `uv run ruff check src/aeat/application/live/_censo.py src/aeat/application/live/test_census_snapshot.py src/aeat/application/live/test_borrador_100_roundtrip.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/live/test_filed_capture_calculation_history.py`
- `uv run pytest src/aeat/application/live/test_census_snapshot.py src/aeat/application/live/test_borrador_100_roundtrip.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/live/test_filed_capture_calculation_history.py -q`
- `uv run pytest src/aeat/application/live -q`
- `uv run python -m aeat.locales audit`
