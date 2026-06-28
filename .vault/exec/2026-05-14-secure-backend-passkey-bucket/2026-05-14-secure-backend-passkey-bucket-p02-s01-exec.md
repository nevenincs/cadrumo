---
tags:
  - '#exec'
  - '#secure-backend-passkey-safety'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'P02.S01'
related:
  - '[[2026-05-14-secure-backend-passkey-bucket-plan]]'
---

# secure-backend-passkey-safety P02.S01

Implement the per-bucket directory provisioning surface at
`src/aeat/adapters/persistence/storage/bucket/_layout.py`. Wire the typed
`BucketPaths` record carrying the resolved subpaths and the fail-closed
`provision_bucket_directory` helper that creates the
`<root>/buckets/<bucket-id>/{db,blobs,audit}/` tree per ADR-2 section 2.

- Created: `src/aeat/adapters/persistence/storage/bucket/_layout.py`
- Created: `src/aeat/adapters/persistence/storage/bucket/test_layout.py`
- Modified: `src/aeat/adapters/persistence/storage/bucket/__init__.py`

## Description

`BucketPaths` is a strict pydantic v2 frozen record (`extra="forbid"`,
`arbitrary_types_allowed=True` for `pathlib.Path`) carrying the bucket id,
the root, and the four resolved directory paths (`bucket_dir`, `db_dir`,
`blobs_dir`, `audit_dir`). `bucket_paths(root, bucket_id)` is the pure
resolver (no filesystem side effects); `provision_bucket_directory` is
the materialiser. The provisioning is fail-closed: a second invocation
against the same bucket id raises `FileExistsError` rather than silently
masking partial state per ADR-2 section 2.

Bucket id validation rejects empty strings and any string carrying a
POSIX or Windows path separator, so an operator-supplied id can never
escape the bucket parent.

## Tests

`test_layout.py` (8 tests; `pytest.mark.unit` + `pytest.mark.domain_persistence`):

- Provisioning materialises the three subdirectories.
- Re-provisioning the same id raises `FileExistsError`.
- Empty / path-separator bucket ids are rejected.
- `bucket_paths` is pure (no filesystem touch).
- `BucketPaths` is strict (`extra="forbid"`) and frozen.
- Two buckets share the `buckets/` parent.

`uv run pytest src/aeat/adapters/persistence/storage/bucket/test_layout.py -x -q` :
8 passed.

`uv run ruff check` and `uv run ty check` clean on the new modules and on
the modified `__init__.py`.
