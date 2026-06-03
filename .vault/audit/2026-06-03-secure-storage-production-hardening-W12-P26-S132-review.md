---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-W12-P26-S132]]'
---

# `secure-storage-production-hardening` `W12.P26.S132` Review

## S132-001 | PASS | OAuth flow returns records and defers persistence to secure session-store boundary

The reviewed module runs the Google OAuth Desktop loopback flow and maps credentials into strict `OAuthToken` and `OAuthMetadata` records. It does not persist those records itself, construct secure-object repositories, choose storage providers, route SQL storage, or write local files. Persistence remains owned by the Google session-store path tracked separately under runtime-default rows.

The active-profile and manifest-bucket signals are read-only safety preflight: the flow resolves the active profile and reads the profile tax id so unsecured secret-store mode refuses real taxpayer identifiers. Settings access is centralized through `load_settings()`, and the source scan found no naked environment access.

Failure surfaces use typed `GoogleAuthError` subclasses rooted at `AeatError`, with translated messages and `tr()`-backed suggestions on operator-facing paths.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/google/test_records.py src/aeat/adapters/outbound/google/test_package_module_allowlist.py src/aeat/entrypoints/cli/_config/test_google_error_localisation.py` passed with 24 tests.
- `uv run --no-sync ruff check src/aeat/adapters/outbound/google/_oauth_flow.py src/aeat/adapters/outbound/google/_errors.py src/aeat/adapters/outbound/google/test_records.py src/aeat/adapters/outbound/google/test_package_module_allowlist.py src/aeat/entrypoints/cli/_config/test_google_error_localisation.py` passed.
- A source scan found no naked environment reads, DB route setup, secure-object repository constructors, local storage provider constructors, or direct local file read/write calls in `_oauth_flow.py`.

Disposition: close `AFR-030` as `remote-mirror`. The live OAuth browser consent probe remains opt-in live evidence and is not counted as this offline ledger closure.
