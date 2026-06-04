---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S228]]'
---

# `secure-storage-production-hardening` `W12.P26.S228` Review

## S228-001 | PASS | Expedientes snapshots are secure-object remote mirrors

`ExpedientesService` persists read-only AEAT declaration walker captures through
`SecureSnapshotRepository`, with storage resolved by `secure_object_repository_for_bucket`.
The service remains read-only and exposes no remote mutation methods.

## S228-002 | PASS | Plain-file signal is stale

The current tests assert the old `aeat_audit_dir/live/expedientes/{bucket}.jsonl`
path is absent after capture. The plan row and module wording now reflect the
secure-object storage layout.

## S228-003 | PASS | Bucket isolation is covered

The test suite provisions separate runtime profiles, proves records do not
cross buckets, and verifies the persisted secure object is addressed with the
bucket-local snapshot object key.

## S228-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/live/_expedientes.py src/aeat/application/live/test_expedientes.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/live/test_expedientes.py` passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` returned only the existing monotonic-order warning.

Reviewer note: no critical, high, medium, or low findings remain for S228.

Disposition: close `AFR-126` as `remote-mirror`.
