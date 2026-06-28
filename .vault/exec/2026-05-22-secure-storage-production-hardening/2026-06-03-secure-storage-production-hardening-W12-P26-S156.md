---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S156'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s156-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S156`

Closed `AFR-054` for the bucket error hierarchy.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/bucket/_errors.py` against the `manifest-bucket` and `master-key` scanner signals.
- Verified all bucket errors derive from the secure-storage AEAT exception hierarchy.
- Verified bucket lifecycle and recovery errors use registry-backed translated message keys.
- Verified the module is an error type surface only and does not perform manifest IO, master-key access, settings/env lookup, or exception swallowing.
- Hardened the bucket error registry tests so `BucketValidationError` is covered by the same inheritance, registered-code, and distinct-code assertions as the other exported bucket errors.
- Closed `S156` through `vaultspec-core vault plan step check`, then manually repaired `AFR-054` to `closed` after the CLI updated the checkbox but left the AFR register row pending.

## Outcome

`AFR-054` is closed as `manifest-discovery`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py src/aeat/adapters/persistence/storage/bucket/test_cluster_envelopes.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/bucket/_errors.py src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py src/aeat/adapters/persistence/storage/bucket/test_cluster_envelopes.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- Touched-file hygiene scan found no broad exception catches, suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, local secure-object marker construction, direct settings construction, or direct environment access.

## Notes

No source edit was required. The scanner hits are references to the manifest/master-key lifecycle in structured error names and docs, not executable storage behavior in the error module.
