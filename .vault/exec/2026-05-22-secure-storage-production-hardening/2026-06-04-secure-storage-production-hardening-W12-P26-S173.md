---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S173'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s173-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S173`

Closed `AFR-071` for per-bucket session custody and engine eviction.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/master_key/_bucket_session.py` against the `manifest-bucket`, `master-key`, `sql-route`, and `plain-file` scanner signals.
- Preserved instance-scoped KEK/DEK buffers and the idempotent zeroise-before-seal close path.
- Routed bucket engine eviction through `settings_for_active_profile_bucket` instead of locally constructing database route settings.
- Replaced the broad engine-eviction catch with explicit `CoreValidationError`, pydantic `ValidationError`, and SQLAlchemy cleanup exception handling.
- Added redacted debug diagnostics for targeted-route fallback and cleanup failures.
- Converted the touched adverse-session test helper to `override_settings` and `UTF_8_ENCODING`.
- Added real-behavior coverage proving `BucketSession.close()` seals under an explicit database URL and logs only redacted route-fallback diagnostics.
- Closed `S173` through `vaultspec-core vault plan step check` and updated `AFR-071` to closed.

## Outcome

`AFR-071` is closed as a `bootstrap-custody` implementation row.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py src/aeat/adapters/persistence/storage/master_key/test_master_key.py src/aeat/adapters/persistence/storage/test_runtime.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/_bucket_session.py src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py src/aeat/adapters/persistence/storage/master_key/test_master_key.py src/aeat/adapters/persistence/storage/test_runtime.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- Touched-surface hygiene scan found no broad exception catches, suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, direct encoding literals, direct settings construction, direct environment access, or local secure-object marker construction.

## Notes

The session still returns immutable `bytes` copies from `kek` and `dek`; the module docstring already states Python cannot guarantee deeper zeroisation of copies. That honest limitation remains unchanged.
