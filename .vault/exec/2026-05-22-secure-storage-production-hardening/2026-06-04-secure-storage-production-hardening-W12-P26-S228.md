---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
step_id: 'S228'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s228-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S228`

Closed `AFR-126` for expedientes snapshot persistence.

## Description

- Reviewed `src/aeat/application/live/_expedientes.py` against the remote
  mirror and secure snapshot contracts.
- Verified expedientes captures persist through `SecureSnapshotRepository`
  backed by `secure_object_repository_for_bucket(bucket_id, settings)`.
- Corrected stale module wording from file-storage layout to secure-object
  storage layout.
- Removed the stale `plain-file` signal from the AFR register row and closed
  `S228` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-126` is closed as `remote-mirror` with `secure-object` storage. Existing
tests prove bucket-scoped runtime isolation, secure-object persistence, old
JSONL absence, and read-only service shape.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/live/_expedientes.py src/aeat/application/live/test_expedientes.py`
- `uv run --no-sync pytest -q src/aeat/application/live/test_expedientes.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` returned only the existing monotonic-order warning.

## Notes

No storage behavior change was needed. No naked environment access, settings
bypass, silent exception swallowing, `noqa`, `pragma`, monkeypatch, fake, mock,
skip, xfail, or tautological test was introduced.
