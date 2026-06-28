---
tags:
  - '#exec'
  - '#google-oauth'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S01+S02+S03+S04+S05'
related:
  - "[[2026-05-13-google-oauth-plan]]"
  - "[[2026-05-12-google-oauth-adr]]"
---

# `google-oauth` `W01.P02` foundation (S01+S02+S03+S04+S05 merged)

Five plan substeps merged into one cohesive deliverable per the no-placeholder mandate. The storage provider abstraction foundation lands together: Protocol, records (including the `ProviderKind` enum), error hierarchy, public surface, registry entries, and unit tests. Concrete backends (`_local.py`, `_google_drive.py`, `_testing.py`) consume the Protocol surface from this commit forward.

- Created: `src/aeat/adapters/outbound/storage/__init__.py` — public surface re-exports the Protocol, the 3 records / enum, the 9 error classes
- Created: `src/aeat/adapters/outbound/storage/_protocol.py` — `StorageProvider` Protocol with 6 methods (put / get / delete / iter_namespaces / iter_objects / probe). `runtime_checkable` so isinstance() works for sanity checks
- Created: `src/aeat/adapters/outbound/storage/_records.py` — `ProviderKind` closed StrEnum (3 values), `ProviderObjectMetadata` + `ProviderProbeReport` frozen strict pydantic records
- Created: `src/aeat/adapters/outbound/storage/_errors.py` — `StorageError` base + 8 typed leaves (Validation, NotFound, Conflict, Permission, Quota, Network, Integrity, Unavailable)
- Created: `src/aeat/adapters/outbound/storage/test_foundation.py` — 12 unit tests covering enum values, record round-trip + frozen + extra-forbid + min-length, probe-report defaults, error hierarchy unification, runtime Protocol conformance (positive + negative)
- Modified: `src/aeat/core/errors/registry/_adapters.py` — appended 9 `StorageError` registrations (`FAIL_OUTBOUND_STORAGE`, `REFUSED_OUTBOUND_STORAGE_*`, `ERROR_OUTBOUND_STORAGE_NOT_FOUND`, `AUTH_OUTBOUND_STORAGE_PERMISSION`, `INTEGRITY_OUTBOUND_STORAGE`)

## Description

The Protocol pins six methods covering the v1 sync coordinator's needs:

- `put(namespace, object_key_hmac, payload, *, content_hash, label) -> ProviderObjectMetadata`
- `get(namespace, object_key_hmac) -> (bytes, ProviderObjectMetadata)`
- `delete(namespace, object_key_hmac) -> bool`
- `iter_namespaces() -> Iterator[str]`
- `iter_objects(namespace) -> Iterator[ProviderObjectMetadata]`
- `probe(*, read_only=False) -> ProviderProbeReport`

Bytes-in / bytes-out: encryption and classification handling stays in the application sync coordinator (per ADR-3 ciphertext-layer mirror), so providers never see plaintext domain data.

`ProviderObjectMetadata` carries the backend-native `provider_object_id` (filesystem path, Drive `fileId`, in-memory key) so subsequent operations on the same object thread through without re-resolving by name. `byte_length`, `content_hash`, and `written_at` round-trip with the substrate's existing envelope shape.

`ProviderProbeReport` has a tri-state `root_folder_present: bool | None` — `None` when the backend has no notion of an operator-configured root folder (local filesystem, in-memory), `True`/`False` for Google Drive depending on whether `aeat_google_drive_root_folder_id` resolves to a real folder. The `read_only` flag is required so callers can distinguish "writable: false because skipped" from "writable: false because backend rejected".

The 9 errors carry distinct `OUTBOUND_STORAGE_*` prefixes to disambiguate from the existing `aeat.adapters.persistence.storage.errors.StorageError` family (which is the encrypted-substrate boundary; this hierarchy is the outbound provider boundary).

## Tests

- `pytest src/aeat/adapters/outbound/storage/test_foundation.py -q` — 12 passed.
- `ruff check src/aeat/adapters/outbound/storage/` — clean.
- Coverage: `ProviderKind` value stability, record JSON round-trip via `model_validate_json`, frozen contract, `byte_length >= 0`, extra-forbid refusal, `ProviderProbeReport.root_folder_present` default-None, read-only mode round-trip, every leaf subclasses `StorageError`, `StorageValidationError` doubles as `ValueError`, distinct stable error codes per leaf, runtime Protocol conformance (positive case + missing-method negative case).

## Outstanding (subsequent P02 commits)

- `_local.py` — `LocalFileSystemProvider` against `pathlib`
- `_testing.py` — `InMemoryDriveProvider` test backend
- `_google_drive.py` — `GoogleDriveProvider` against `google-api-python-client`
- `_factory.py` — `get_storage_provider` keyed on `ProviderKind`
- `core/config.py` — `aeat_storage_provider_kind` + `aeat_google_drive_root_folder_id` settings
- Live-gated tests for Drive backend
- Import-contract smoke test addition
