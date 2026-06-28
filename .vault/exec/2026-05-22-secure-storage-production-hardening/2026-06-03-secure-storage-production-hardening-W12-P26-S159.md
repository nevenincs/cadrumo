---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S159'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s159-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S159`

Closed `AFR-057` for the per-bucket layout and provisioning helpers.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/bucket/_layout.py` against the `manifest-bucket` and `sql-route` scanner signals.
- Preserved the canonical `buckets/<bucket-id>/{db,blobs,audit}` layout derived from shared storage hierarchy constants.
- Replaced raw `FileExistsError` collision surfacing in `provision_bucket_directory()` with localized `BucketAlreadyPresentError`, preserving the original filesystem exception as `__cause__` for diagnostics.
- Closed a review finding where a file at `<root>/buckets` could still raise raw `FileExistsError` before the typed wrapper.
- Added real filesystem tests proving repeat provisioning and buckets-parent file collisions remain fail-closed, return the typed bucket collision error, and do not leak the local root path in `str(error)` or the structured error envelope.
- Closed `S159` through `vaultspec-core vault plan step check`, then manually repaired `AFR-057` to `closed` after the CLI updated the checkbox but left the AFR register row pending.

## Outcome

`AFR-057` is closed as `manifest-discovery`: layout provisioning remains the canonical bucket directory primitive, and collision failures are now enrolled in the AEAT error hierarchy without raw path exposure.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/bucket/test_layout.py src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py src/aeat/adapters/persistence/storage/bucket/test_cluster_envelopes.py` passed with 39 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/bucket/_layout.py src/aeat/adapters/persistence/storage/bucket/test_layout.py src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py src/aeat/adapters/persistence/storage/bucket/test_cluster_envelopes.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- Touched-file hygiene scan found no broad exception catches, suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, raw encoding literals, direct settings construction, or direct environment access.

## Notes

The change intentionally narrows only bucket-collision surfacing. Other filesystem failures still propagate as their concrete `OSError` subclasses so permission and disk failures are not mislabeled as existing-bucket collisions.
