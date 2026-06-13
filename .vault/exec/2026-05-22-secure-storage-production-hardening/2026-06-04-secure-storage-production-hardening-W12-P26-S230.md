---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S230'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s230-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S230`

Closed `AFR-128` for the shared live snapshot base.

## Description

- Reviewed `src/aeat/application/live/_snapshot_base.py` against the
  `runtime-default` classification for secure-object live snapshot storage.
- Changed `SecureSnapshotRepository.list_snapshots()` to fail closed when a
  decrypted payload bucket does not match the repository bucket.
- Added a real secure-object regression test that seeds a mismatched payload
  through the registered test namespace and verifies list-time refusal.
- Added the snapshot-base bucket-mismatch locale key through
  `python -m aeat.locales`.
- Closed `S230` through `vaultspec-core vault plan step check` and marked
  `AFR-128` closed.

## Outcome

`AFR-128` is closed as `runtime-default`. The shared live snapshot repository
continues to use runtime-bound secure-object storage and now refuses semantic
bucket contamination during list/latest consumers instead of silently hiding
misrouted rows.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/live/_snapshot_base.py src/aeat/application/live/test_snapshot_base.py`
- `uv run --no-sync pytest -q src/aeat/application/live/test_snapshot_base.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "borrador or censo or expedientes or notifications or s85_runtime"`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Notes

Locale catalogue updates were performed through `python -m aeat.locales`
(`set` and `audit`). No naked environment access, settings bypass,
silent exception swallowing, `noqa`, `pragma`, monkeypatch, fake, mock, skip,
xfail, or tautological test was introduced.
