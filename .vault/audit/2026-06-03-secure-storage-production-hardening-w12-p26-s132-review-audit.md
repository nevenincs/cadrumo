---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
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

## S132-002 | MEDIUM | RESOLVED | Unclassified OAuth local-server failures escaped the AEAT exception boundary

`_run_local_server()` translated browser, transport, and loopback-bind failures, but an unclassified exception raised by `InstalledAppFlow.run_local_server()` was re-raised raw. The CLI catches `GoogleAuthError` for this path, so an upstream OAuth failure outside the string classifier could bypass the existing AEAT exception hierarchy.

Resolution: `_raise_local_server_error()` now maps unclassified local-server failures to `GoogleAuthNetworkError` with the original exception preserved as `__cause__`. Browser and network string classifications still raise their existing typed subclasses.

Validation:

- `test_oauth_flow.py` covers browser, network, and unclassified upstream local-server failure translation.
- Focused OAuth/profile tests passed with 28 tests.
- The broader focused Google adapter suite passed with 131 tests.

## S132-003 | HIGH | RESOLVED | Missing active profile state could bypass unsecured-mode refusal

Follow-up review found that `resolve_active_tax_id()` returned an empty tax id when the active bucket manifest or profile aggregate was missing. Under `aeat_secret_store_backend=unsecured`, that stale-profile state could proceed toward loopback OAuth because the real-tax-id refusal only fires for non-empty tax ids.

Resolution: missing active-profile bucket manifests and missing profile aggregates now raise `GoogleAuthProfileUnboundError` with a localized `profile_state_unresolved` message and `tr()`-resolved repair guidance before `_run_local_server()` is reached.

Validation:

- `test_oauth_flow.py` covers a missing bucket manifest and a real isolated active-bucket runtime whose profile aggregate is absent.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/google/test_oauth_flow.py` passed.
- Targeted Ruff passed for `_oauth_flow.py` and `test_oauth_flow.py`.
