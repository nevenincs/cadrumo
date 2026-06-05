---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
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

## S287-004 | PASS | Duplication and validation

Vaultspec RAG clustered this slice with the pointer I/O module, profile-bucket
manifest scanner, active-profile health resolver, and CLI `--profile` normalization.
No duplicate active-profile pointer I/O implementation was found.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/_bucket_pointer_io.py src/aeat/core/_bucket_pointer.py src/aeat/core/test_bucket_pointer_io.py src/aeat/core/test_bucket_pointer.py src/aeat/application/workflow/test_active_profile_resolution.py`
- `uv run --no-sync pytest -q src/aeat/core/test_bucket_pointer_io.py src/aeat/core/test_bucket_pointer.py src/aeat/application/workflow/test_active_profile_resolution.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "active profile pointer file bucket pointer io load_settings os.replace manifest discovery" --type code --port 8766 --max-results 8`
