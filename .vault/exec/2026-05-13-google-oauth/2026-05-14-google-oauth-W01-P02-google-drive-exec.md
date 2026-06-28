---
tags:
  - '#exec'
  - '#google-oauth'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S07+S18'
related:
  - "[[2026-05-13-google-oauth-plan]]"
  - "[[2026-05-12-google-oauth-adr]]"
---

# `google-oauth` `W01.P02.S07+S18` — GoogleDriveProvider

`GoogleDriveProvider` against the Drive v3 API with root-folder discovery. Implements the full `StorageProvider` Protocol, lazy-loads the upstream `googleapiclient` discovery client, translates `HttpError` status codes onto the typed `StorageError` hierarchy. Root-folder discovery (S18) creates `aeat-vault/` lazily under the operator-configured `aeat_google_drive_root_folder_id` parent.

- Created: `src/aeat/adapters/outbound/storage/_google_drive.py` — `GoogleDriveProvider` + `_translate_http_error` + `_service_factory` + `_build_media_body` + `_metadata_from_drive_entry`
- Created: `src/aeat/adapters/outbound/storage/test_google_drive.py` — 17 unit tests with a `_FakeDriveService` Resource-shaped stub + `_HttpError` Drive-error-shaped stand-in
- Modified: `pyproject.toml` — added `test_google_drive.py` per-file-ignore for E501 (long inline `_FakeFile(...)` fixtures read better unwrapped)

## Description

Drive folder layout follows ADR-2: each namespace is a folder directly under `aeat-vault/`, each object is a binary file named `<hmac_prefix_8>--<label>.bin`. The provider caches `aeat-vault/` and per-namespace folder IDs across the instance lifetime so repeat `put` calls inside one process only hit the Drive API once for folder resolution.

`_translate_http_error` maps Drive `HttpError` status codes:
- `401` / `403` → `StoragePermissionError`
- `404` → `StorageNotFoundError`
- `409` → `StorageConflictError`
- `429` → `StorageQuotaError`
- `5xx` → `StorageUnavailableError`
- everything else → `StorageNetworkError`

`put` distinguishes create-vs-update: a Drive `files().create` call for new objects (with `parents=[namespace_folder_id]`), or `files().update` for existing ones (without `parents`, with optional `name` rename when the label drifted). The `appProperties` field carries `namespace`, `object_key_hmac`, and `content_hash` so subsequent `iter_objects` / `get` calls can verify integrity without an extra Drive round-trip.

`get` downloads via `files().get_media(fileId=...)`. When the stored `appProperties.content_hash` is a recognisable bare 64-hex sha256 digest, the provider verifies the downloaded payload's actual sha256 matches before returning; mismatches raise `StorageIntegrityError`.

`iter_namespaces` and `iter_objects` paginate Drive listings via `pageToken`.

`probe`:
- First, fetches the configured root folder via `files().get(fileId=root_folder_id, fields="id,mimeType,trashed")`. Returns `root_folder_present=False` on 404, trashed, or non-folder `mimeType`.
- When `read_only=False`, performs a full sentinel round-trip (`put` + `delete` in `_probe/`).
- Returns a structured `ProviderProbeReport` describing the outcome; never raises on transient failures.

Tests use a `_FakeDriveService` that mirrors the parts of the Drive v3 `Resource` interface the provider consumes. The fake has its own tiny query interpreter for `files().list` so the four query patterns the provider emits (parent-in / name-equals / name-contains / mime-filter) are exercised against in-memory data. `_HttpError` mirrors `googleapiclient.errors.HttpError` enough that `_translate_http_error` can read `.resp.status`. The `service_factory` constructor parameter accepts the fake without going through `googleapiclient`, so the test suite runs without `import googleapiclient` ever resolving.

## Tests

- `pytest src/aeat/adapters/outbound/storage/ -q` — 64 passed (12 foundation + 17 local + 18 in-memory + 17 drive).
- `ruff check src/aeat/adapters/outbound/storage/` — clean.
- Drive coverage: runtime Protocol conformance, init rejects blank root_folder_id, put creates vault + namespace lazily, put reuses existing folders, get round-trip, get StorageNotFoundError for missing namespace, get StorageIntegrityError on hash mismatch, delete returns True/False correctly, iter_namespaces ignores non-folder children, iter_objects yields metadata, iter_objects StorageNotFoundError for missing namespace, probe returns root_folder_absent on 404, probe returns writable on full round-trip, probe read_only skips sentinel, _translate_http_error 403 → StoragePermissionError, put rejects blank namespace.

## Outstanding (subsequent P02 commits)

- `_factory.py` — `get_storage_provider` keyed on `ProviderKind` (P02.S09+S16+S17)
- `core/config.py` — `aeat_storage_provider_kind` + `aeat_google_drive_root_folder_id` settings (P02.S16)
- Factory composition wiring active profile + credentials through to GoogleDriveProvider (P02.S17)
- Live-gated tests against real Drive (P02.S14)
- Import-contract smoke test addition (P02.S15)
