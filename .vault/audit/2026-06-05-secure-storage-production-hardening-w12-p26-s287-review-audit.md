---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S287-001 | PASS | Active-profile pointer I/O boundary

`src/aeat/core/_bucket_pointer_io.py` owns the plaintext active-profile pointer file
used before encrypted bucket state can be opened. This is the expected bootstrap
boundary for selecting the runtime secure bucket. The module reads and writes only
`<aeat-root>/active-profile`; it does not open secure-object repositories, route SQL,
read profile bucket manifests, call remote providers, or handle master-key material.

Disposition: close `AFR-185` as manifest-discovery bootstrap pointer I/O.

## S287-002 | PASS | Settings-backed active bucket resolution

`resolve_active_bucket_id()` obtains configuration through `load_settings()` and reads
`settings.aeat_active_profile` before falling through to the pointer file under
`settings.aeat_local_storage_root`. No naked environment access is present in this
module. `require_active_bucket_id()` raises the core `NoActiveProfileError` with a
translation key when neither rung resolves.

## S287-003 | PASS | Atomic write and strict parsing

`write_pointer()` creates the AEAT root lazily, writes a sibling `.tmp` file, and
atomically replaces the target with `os.replace`. `read_pointer()` returns `None` for
an absent file and otherwise delegates parsing to the strict `BucketPointer` pydantic
value object. Parse and validation failures are not swallowed.

## S287-004 | PASS | Runtime factory consumes pointer-selected buckets

The added runtime test proves a pointer-selected active bucket is treated as a
profile-bound runtime route: without an active bucket session,
`secure_object_repository_for_active_bucket_or_default_route()` raises
`StorageValidationError` instead of returning a root/default repository.

## S287-005 | PASS | Corrupt pointer errors are not swallowed

`read_pointer()` propagates strict validation failures. Existing CLI boundary
coverage verifies a corrupt pointer does not get reclassified as a no-profile
refusal.

## S287-006 | PASS | Duplication and validation

Vaultspec RAG clustered this slice with the pointer I/O module, profile-bucket
manifest scanner, active-profile health resolver, and CLI `--profile` normalization.
No duplicate active-profile pointer I/O implementation was found. The new regression
uses the real pointer writer, real settings override, and real runtime factory. It
does not mock, monkeypatch, skip, xfail, or duplicate runtime implementation logic.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/_bucket_pointer_io.py src/aeat/core/test_bucket_pointer_io.py src/aeat/core/test_storage_route_classification.py src/aeat/adapters/persistence/storage/runtime_repository.py src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/entrypoints/cli/test_ledger_exception_propagation.py`
- `uv run --no-sync pytest -q src/aeat/core/test_bucket_pointer_io.py src/aeat/core/test_storage_route_classification.py src/aeat/adapters/persistence/storage/test_runtime.py::test_default_route_repository_refuses_pointer_scoped_active_profile_without_session src/aeat/entrypoints/cli/test_ledger_exception_propagation.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "active profile pointer file bucket pointer io load_settings os.replace manifest discovery" --type code --port 8766 --max-results 8`
