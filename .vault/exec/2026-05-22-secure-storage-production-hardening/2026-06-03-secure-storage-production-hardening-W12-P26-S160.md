---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S160'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s160-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S160`

Closed `AFR-058` for the per-bucket lockfile primitive.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/bucket/_lockfile.py` against the `manifest-bucket` and `plain-file` scanner signals.
- Hardened lockfile PID reads into explicit missing, unreadable, invalid, and parsed states.
- Added debug diagnostics for malformed/empty/unreadable PID files, denied liveness probes, and missing-file cleanup races without logging bucket paths.
- Kept lockfiles as non-sensitive PID-only coordination metadata and tightened creation to mode `0o600`.
- Added create-failure cleanup so a lockfile created by `O_EXCL` is not left behind when PID writing or descriptor close fails before acquisition completes.
- Added real-behavior tests for malformed PID reclaim, missing release diagnostics, lockfile mode, and bucket-directory collision error envelopes.
- Closed `S160` through `vaultspec-core vault plan step check` and updated `AFR-058` to closed.

## Outcome

`AFR-058` is closed as `manifest-discovery`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/bucket/test_lockfile.py src/aeat/adapters/persistence/storage/bucket/test_layout.py src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py src/aeat/adapters/persistence/storage/bucket/test_cluster_envelopes.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/bucket/_lockfile.py src/aeat/adapters/persistence/storage/bucket/test_lockfile.py src/aeat/adapters/persistence/storage/bucket/test_layout.py src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py src/aeat/adapters/persistence/storage/bucket/test_cluster_envelopes.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- Touched-file hygiene scan found no broad exception catches, suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, local secure-object marker construction, direct settings construction, or direct environment access.

## Notes

No modelo export evidence or workbook parity behavior is implemented in this row. The new export ADR constraints remain applicable to later export rows; this lockfile row only governs local bucket concurrency metadata.
