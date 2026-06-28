---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S159]]'
---

# `secure-storage-production-hardening` `W12.P26.S159` Review

## S159-001 | FIXED BEFORE COMMIT | Existing-bucket provisioning is typed and localized

`provision_bucket_directory()` previously relied on raw `FileExistsError` from `Path.mkdir(exist_ok=False)` for repeat provisioning. That preserved fail-closed behavior but surfaced a filesystem exception that can include local directory paths.

Resolution: bucket-directory collisions now raise `BucketAlreadyPresentError(bucket_id=...)` from the original `FileExistsError`. The public exception is registry-backed and localized; the filesystem exception remains available as `__cause__` for internal diagnostics.

## S159-002 | PASS | Bucket layout constants remain centralized

The module derives `buckets`, `db`, `blobs`, and `audit` path segments from the storage namespace registry constants. `BucketPaths` remains a strict frozen record, and `bucket_paths()` remains a pure path resolver with no filesystem side effects.

## S159-003 | FIXED BEFORE COMMIT | Buckets-parent file collision is also typed

Review found that `paths.bucket_dir.parent.mkdir(parents=True, exist_ok=True)` sat outside the `FileExistsError` remap. If `<root>/buckets` already existed as a file, provisioning could still raise a raw path-bearing filesystem exception before the typed bucket collision wrapper.

Resolution: parent-directory creation is inside the same narrow `FileExistsError` conversion. A real filesystem test creates a file at `<root>/buckets` and verifies provisioning raises `BucketAlreadyPresentError`, retains the original `FileExistsError` as cause, and does not leak the local root path in string or envelope output.

## S159-004 | PASS | Provisioning behavior is still fail-closed

Repeat provisioning still refuses the existing bucket. Tests verify the typed collision error carries the bucket id, exposes a localized error envelope, does not include the local root path in `str(error)` or JSON envelope output, and retains the original `FileExistsError` as the cause.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/bucket/test_layout.py src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py src/aeat/adapters/persistence/storage/bucket/test_cluster_envelopes.py` passed with 39 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/bucket/_layout.py src/aeat/adapters/persistence/storage/bucket/test_layout.py src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py src/aeat/adapters/persistence/storage/bucket/test_cluster_envelopes.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` reported `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` ok.
- Touched-file hygiene scan found no broad exception catches, suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, raw encoding literals, direct settings construction, or direct environment access.
- Plan state was reconciled after the CLI checked S159 but left `AFR-057` pending; the repaired state is `AFR-057`/`S159` closed and `AFR-058` through `AFR-060` / `S160` through `S162` pending.

Disposition: close `AFR-057` as `manifest-discovery`.
