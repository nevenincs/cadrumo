---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S287'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S287 - Close AFR-185 for active-profile pointer I/O

Scope: close `AFR-185` for `src/aeat/core/_bucket_pointer_io.py` with signals
`active-profile, manifest-bucket, plain-file`, target `manifest-discovery`, and owner
`W12.P22.S90`.

## Description

- Audited active-profile pointer file reads, writes, and resolution.
- Confirmed resolution is settings-backed through `load_settings()` and does not read
  environment variables directly.
- Confirmed the pointer file is a bootstrap selector for the runtime secure bucket,
  not an encrypted repository or remote mirror.
- Verified `read_pointer()` strict-validates pointer TOML and does not swallow
  corrupt pointer payloads.
- Verified `write_pointer()` remains atomic through write-then-rename and stores
  only the bucket pointer record.
- Verified writes use write-then-rename via `os.replace` and strict parsing delegates
  to the shared `BucketPointer` pydantic value object.
- Added a runtime-management regression proving a pointer-selected active bucket
  makes `secure_object_repository_for_active_bucket_or_default_route()` refuse
  without an active bucket session instead of falling back to root/default storage.
- Ran vaultspec RAG semantic search and focused pointer I/O tests.
- Closed `W12.P26.S287` through `vaultspec-core vault plan step check` and
  updated the `AFR-185` register status to `closed`.

## Outcome

`AFR-185` is closed as the manifest-discovery bootstrap pointer I/O boundary and
as a plaintext active-profile selector feeding centralized runtime repository
management. No production code change was required for `src/aeat/core/_bucket_pointer_io.py`;
the runtime factory now has explicit regression coverage for the pointer-derived
bucket route.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/_bucket_pointer_io.py src/aeat/core/test_bucket_pointer_io.py src/aeat/core/test_storage_route_classification.py src/aeat/adapters/persistence/storage/runtime_repository.py src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/entrypoints/cli/test_ledger_exception_propagation.py`
- `uv run --no-sync pytest -q src/aeat/core/test_bucket_pointer_io.py src/aeat/core/test_storage_route_classification.py src/aeat/adapters/persistence/storage/test_runtime.py::test_default_route_repository_refuses_pointer_scoped_active_profile_without_session src/aeat/entrypoints/cli/test_ledger_exception_propagation.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "active profile pointer file bucket pointer io load_settings os.replace manifest discovery" --type code --port 8766 --max-results 8`

## Notes

The plaintext pointer is intentionally retained because it selects which secure bucket
runtime-owned repositories open before encrypted state is available. The downstream
broad fallback in `core.config` remains tracked under the pending `core/config.py`
row. This step intentionally keeps `_bucket_pointer_io.py` strict and surfaces
corrupt pointer payloads to profile-bound callers.
