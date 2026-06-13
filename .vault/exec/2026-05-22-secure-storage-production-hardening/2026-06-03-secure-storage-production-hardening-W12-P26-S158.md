---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S158'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s158-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S158`

Closed `AFR-056` for the bucket keystore path helpers.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/bucket/_keystore_paths.py` against the `manifest-bucket` and `plain-file` scanner signals.
- Preserved the keystore separation invariant: bucket custody material resolves under the keystore root and configured keystore paths fail closed when they resolve under the buckets parent or per-bucket database directory.
- Removed full filesystem paths from keystore separation validation messages and replaced them with stable reason text plus structured context.
- Enrolled `BucketValidationError` explicitly in `errors.integrity.integrity_storage_bucket_validation` rendering while preserving `str(error)` detail compatibility for existing validation tests.
- Added real tests proving keystore validation errors do not leak the configured path or AEAT root path in `str(error)` or the structured error envelope.
- Closed `S158` through `vaultspec-core vault plan step check`, then manually repaired `AFR-056` to `closed` after the CLI updated the checkbox but left the AFR register row pending.

## Outcome

`AFR-056` is closed as `manifest-discovery`: the helpers remain pure path derivation/validation code, but path-shaped validation failures are now redacted and locale-enrolled.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/bucket/test_keystore_paths.py src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py src/aeat/adapters/persistence/storage/bucket/test_cluster_envelopes.py` passed with 38 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/bucket/_keystore_paths.py src/aeat/adapters/persistence/storage/bucket/_errors.py src/aeat/adapters/persistence/storage/bucket/test_keystore_paths.py src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py src/aeat/adapters/persistence/storage/bucket/test_cluster_envelopes.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- Touched-file hygiene scan found no broad exception catches, suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, raw encoding literals, direct settings construction, or direct environment access.

## Notes

The per-bucket database-path case is checked before the broader buckets-parent check, so callers receive the most specific reason code without exposing either path.
