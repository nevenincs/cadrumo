---
tags:
  - '#exec'
  - '#google-oauth'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S06+S08+S10+S11+S12'
related:
  - "[[2026-05-13-google-oauth-plan]]"
  - "[[2026-05-12-google-oauth-adr]]"
---

# `google-oauth` `W01.P02` backends (S06+S08+S10+S11+S12 merged for both backends)

Five plan substeps merged for two concrete `StorageProvider` implementations: `LocalFileSystemProvider` (S06) backed by pathlib, and `InMemoryDriveProvider` (S08) backed by a per-instance Python dict. Both implement `iter_namespaces` (S10), `iter_objects` (S11), and `probe(read_only=False)` (S12) for full Protocol coverage. The Google Drive backend (S07) lands separately because it depends on the OAuth flow committed in P01.

- Created: `src/aeat/adapters/outbound/storage/_local.py` — `LocalFileSystemProvider` with atomic put via `.tmp` rename, JSON sidecar metadata, hashlib integrity check on get, prefix-based object resolution to support label drift, sentinel-file probe round-trip in `_probe/` namespace
- Created: `src/aeat/adapters/outbound/storage/_testing.py` — `InMemoryDriveProvider` mirroring Drive semantics (UUID-shaped `provider_object_id`, insertion-order namespaces, retained-empty-namespaces after delete, integrity check on get when stored hash is 64-hex)
- Created: `src/aeat/adapters/outbound/storage/test_local.py` — 17 unit tests against a real `tmp_path` directory tree
- Created: `src/aeat/adapters/outbound/storage/test_in_memory.py` — 18 unit tests against the in-memory backend

## Description

### LocalFileSystemProvider

File-naming convention follows ADR-2 §filename: `<hmac_prefix_8>--<label>.bin` for payloads and `<hmac_prefix_8>--<label>.meta.json` for sidecars. Object resolution is HMAC-prefix-based so a label-drift rename (`v1` → `v2`) finds the existing file via prefix without re-listing the directory.

Atomic put: payload writes to `<final>.bin.tmp`, then `os.replace(.tmp, .bin)` for atomic rename. On sidecar-write failure the payload is unlinked so no orphaned objects survive. Concurrent put with a different label deletes the previous file + sidecar before writing — the coordinator's diff classifier handles the rename detection.

`probe(read_only=False)` does a full sentinel round-trip via `put + delete` in the `_probe/` namespace. `probe(read_only=True)` only validates that the root directory is reachable (creating it with `mkdir(parents=True, exist_ok=True)` if absent) — no sentinel file is touched.

Validation rejects blank namespaces, namespaces with `/` or `\`, dot-prefixed names, blank HMACs, and HMACs with non-alphanumeric characters (besides `-` `_`). Blank `content_hash` is also rejected.

### InMemoryDriveProvider

Pure Python dict-based backend mirroring Drive semantics where they diverge from a local filesystem:

- `provider_object_id` is a `uuid.uuid4()` string (Drive `fileId`-shaped), never a filesystem path.
- `iter_namespaces` yields insertion order (not sorted) — Drive has no canonical namespace ordering, so tests that assume sorted output would mask production-side ordering bugs.
- Emptied namespaces stick around in `iter_namespaces` because Drive folders remain after their last file is deleted.
- Integrity check fires only when `content_hash` is recognisable as a bare 64-hex sha256 digest; tests can inject a wrong hash to force the integrity-failure path.
- `probe` never touches a real filesystem; always returns `provider_kind=IN_MEMORY` reachable.

## Tests

- `pytest src/aeat/adapters/outbound/storage/ -q` — 47 passed (12 foundation + 17 local + 18 in-memory).
- `ruff check src/aeat/adapters/outbound/storage/` — clean.
- Local provider coverage: runtime Protocol conformance, atomic put creates namespace + writes payload + sidecar, sidecar fields canonical, get round-trip, get StorageNotFoundError on miss, get StorageIntegrityError on payload tamper, delete returns True/False correctly, iter_namespaces, iter_objects, iter_objects StorageNotFoundError on missing namespace, probe read-only does not touch fs, probe full round-trip cleans up sentinel, put-with-relabel replaces, validation refusals (blank namespace / slash / blank content_hash).
- In-memory provider coverage: runtime Protocol conformance, Drive-shaped object_id, get round-trip, StorageNotFoundError (missing namespace / missing object), StorageIntegrityError on injected bad hash, delete returns True/False, iter_namespaces insertion order, iter_namespaces retains emptied namespaces, iter_objects, iter_objects StorageNotFoundError, probe + probe read-only, validation refusals (blank namespace / blank hmac / blank content_hash), overwrite replaces payload + metadata.

## Outstanding (subsequent P02 commits)

- `_google_drive.py` — `GoogleDriveProvider` against `google-api-python-client` + the OAuth credentials from P01
- `_factory.py` — `get_storage_provider` keyed on `ProviderKind` (P02.S09)
- `core/config.py` — `aeat_storage_provider_kind` + `aeat_google_drive_root_folder_id` settings (P02.S16+S17+S18)
- Live-gated tests for the Drive backend (P02.S14)
- Import-contract smoke test addition (P02.S15)
