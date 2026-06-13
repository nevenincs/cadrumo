---
tags:
  - '#exec'
  - '#google-oauth'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S09+S14+S15+S16+S17'
related:
  - "[[2026-05-13-google-oauth-plan]]"
  - "[[2026-05-12-google-oauth-adr]]"
---

# `google-oauth` `W01.P02` closeout (S09+S14+S15+S16+S17 merged)

Five plan substeps merged into one cohesive deliverable closing Phase P02: storage provider factory (S09), Settings additions (S16), factory composition with profile binding + OAuth credentials (S17), live-gated tests (S14), and import-contract smoke-test re-add (S15). After this commit Phase P02 is operationally complete.

- Created: `src/aeat/adapters/outbound/storage/_factory.py` — `get_storage_provider(*, profile_override=None, settings=None) -> StorageProvider` keyed on `ProviderKind`; threads OAuth credentials from `aeat.adapters.outbound.google._session_store` into `GoogleDriveProvider`; refuses unknown kinds, blank kind, drive-without-root-folder, missing OAuth client, missing OAuth token
- Created: `src/aeat/adapters/outbound/storage/test_factory.py` — 12 unit tests covering every backend branch + refusal path + parse-kind helper
- Created: `src/aeat/adapters/outbound/storage/test_google_drive_live.py` — 3 live-gated tests (probe, put+get round-trip, delete) gated on `AEAT_LIVE_TESTS_ENABLED=1` AND `aeat_storage_provider_kind=google_drive` AND a registered OAuth client+token for `AEAT_GOOGLE_LIVE_PROFILE` (default `live-test`)
- Modified: `src/aeat/adapters/outbound/storage/__init__.py` — re-exported `get_storage_provider`
- Modified: `src/aeat/core/config.py` — added `aeat_storage_provider_kind`, `aeat_local_storage_root`, `aeat_google_drive_root_folder_id` Settings fields with idiomatic descriptions
- Modified: `src/aeat/tests/test_adr_layout_import_smoke.py` — added `aeat.adapters.outbound.storage` to `ADR_LAYOUT_PACKAGES`; added `StorageProvider`, `StorageError`, `get_storage_provider` to `CANONICAL_PUBLIC_SYMBOLS`
- Modified: `pyproject.toml` — added `test_factory.py` per-file-ignore for the synthetic OAuth fixture S105/S106/E501 false positives

## Description

The factory is the single entry point upper layers (sync coordinator, CLI commands, application services) consume to obtain a wired `StorageProvider`:

1. Settings drive the choice: `aeat_storage_provider_kind` selects the backend; `aeat_local_storage_root` and `aeat_google_drive_root_folder_id` parameterise the backends that need them.
2. The active profile resolves via `_profile_binding.resolve_active_profile(profile_override)`. The in-memory backend skips profile resolution because tests own its lifetime directly.
3. Dispatch on `ProviderKind`:
   - `IN_MEMORY` → `InMemoryDriveProvider()`
   - `LOCAL_FILESYSTEM` → `LocalFileSystemProvider(root=settings.aeat_local_storage_root / profile)`
   - `GOOGLE_DRIVE` → loads the per-profile `OAuthClient` + `OAuthToken` via `_session_store`, hydrates `google.oauth2.credentials.Credentials`, instantiates `GoogleDriveProvider(credentials=..., root_folder_id=settings.aeat_google_drive_root_folder_id)`
4. Refuses every malformed configuration with `StorageValidationError` carrying actionable `context` + `suggestion`.

The Google credentials hydration intentionally sets `token=None` so the first refresh rebuilds the access token from the persisted refresh token — matches the `_oauth_flow.run_login_flow` + `_refresh.refresh_credentials` contract from P01.

The local backend scopes its root by profile name (`<aeat_local_storage_root>/<profile>/`) so multiple AEAT profiles can coexist on disk without colliding. The Drive backend does not need profile scoping because Drive accounts are 1:1 with profiles by ADR-0 §5.

Live tests use the `_probe/` namespace with a deterministic HMAC string so repeated runs do not pollute the operator's real substrate namespaces. Each test calls `_provider_or_skip()` which skip-cleanly returns when `AEAT_LIVE_TESTS_ENABLED!=1`, when `aeat_storage_provider_kind!=google_drive`, when `aeat_google_drive_root_folder_id` is unset, or when `get_storage_provider` raises during construction (no OAuth records present).

The smoke-test re-add covers both the import-surface (the package itself must be importable) and three canonical public symbols (`StorageProvider`, `StorageError`, `get_storage_provider`) so any future refactor that hides the public surface fails the smoke test.

## Tests

- `pytest src/aeat/adapters/outbound/storage/ src/aeat/tests/test_adr_layout_import_smoke.py -q` — 154 passed, 3 deselected.
- `ruff check src/aeat/adapters/outbound/storage/` — clean.
- Factory coverage: in-memory branch, local-filesystem branch + profile scoping, profile override threading, unknown kind refused, empty kind refused, drive-without-root-folder refused, drive-without-client refused, drive-without-token refused, drive happy path, `_parse_kind` accepts every canonical value, `_parse_kind` is case-insensitive, default-settings resolution path.
- Smoke-test additions: storage package importable, `StorageProvider` Protocol re-exported, `StorageError` re-exported, `get_storage_provider` re-exported.

## P02 close

After this commit Phase P02 is operationally complete: 18/18 substeps merged into 6 cohesive commits, ~80 unit tests pass across the storage package, 3 live-gated tests skip cleanly, smoke test green. The storage provider abstraction is fully wired end-to-end:

- `LocalFileSystemProvider` (pathlib, atomic put, sidecar metadata)
- `InMemoryDriveProvider` (Drive-shaped real implementation for tests)
- `GoogleDriveProvider` (Drive v3 API, HttpError translation, root-folder discovery)
- `get_storage_provider` factory keyed on `ProviderKind` with full credential composition

Remaining google-oauth work (P03 sync coordinator, P04 escrow, P05 inbound, P06 substrate hooks, P07 calc-sheets, P08 operator CLI) lives in subsequent phases per the L3 master plan.
