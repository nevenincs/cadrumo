---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S199'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s199-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S199`

Closed `AFR-097` for auth session storage-state identity.

## Description

- Reviewed `src/aeat/application/auth/_sessions.py` against the
  `manifest-discovery` classification: active-profile identity, manifest-bucket
  storage, master-key session handling, and the legacy plaintext token-dir
  signal.
- Added `src/aeat/core/auth_session_keys.py` as the centralized logical-key
  helper for encrypted AEAT browser-session objects.
- Changed `storage_state_paths()` so provider session keys are active-profile
  and provider scoped under `.aeat/auth/sessions/`, independent of
  `Settings.aeat_token_dir`.
- Routed certificate auth and Cl@ve Móvil provider storage-state path builders
  through the same centralized helper so application probes, provider saves,
  and provider resumes agree on the encrypted object key.
- Updated focused storage-state path tests to assert encrypted logical keys,
  provider separation, active-profile separation, and token-dir independence.
- Cross-commit note: the same Cl@ve Móvil provider files also carried
  representation-action centralization through external constants and typed
  initial selector-navigation timeout coverage. Those hunks were validated with
  the focused Cl@ve tests listed below and were not reverted.

Affected files:

- `src/aeat/core/auth_session_keys.py`
- `src/aeat/application/auth/_sessions.py`
- `src/aeat/application/auth/test_sessions_storage_state_paths.py`
- `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`
- `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`
- `src/aeat/adapters/outbound/aeat/auth/test_authenticator.py`
- `src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py`
- `src/aeat/adapters/outbound/aeat/auth/test_clave_movil_live.py`

## Outcome

`AFR-097` is closed. Application auth sessions no longer expose or depend on a
plaintext token directory for encrypted session object identity; the path value
is now a stable logical key consumed by the secure session store.

Validation passed:

- `$env:PYTHONPATH='src'; uv run --no-sync ruff check src/aeat/core/auth_session_keys.py src/aeat/application/auth/_sessions.py src/aeat/application/auth/test_sessions_storage_state_paths.py src/aeat/application/auth/test_persisted_session_metadata.py src/aeat/adapters/outbound/aeat/auth/_authenticator.py src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/adapters/outbound/aeat/auth/test_authenticator.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil_live.py`
- `$env:PYTHONPATH='src'; uv run --no-sync pytest -q src/aeat/application/auth/test_operator.py src/aeat/application/auth/test_operator_storage_session.py src/aeat/application/auth/test_sessions_storage_state_paths.py src/aeat/application/auth/test_persisted_session_metadata.py`
- `$env:PYTHONPATH='src'; uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/auth/test_session_store_roundtrip.py src/aeat/adapters/outbound/aeat/auth/test_authenticator.py::test_authenticate_falls_back_after_stale_persisted_session src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py::TestProbePersistedSession::test_probe_uses_existing_encrypted_session_without_invalidating_on_failure`
- `$env:PYTHONPATH='src'; uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py::test_auth_browser_action_policy_allows_configured_own_name_representation_action src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py::test_auth_browser_action_policy_rejects_unclassified_representation_action src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py::TestAuthenticateFresh::test_initial_selector_navigation_timeout_is_typed`

## Notes

No new direct secure-object repository construction, naked environment access,
silent exception swallowing, raw user-facing strings, `noqa`, `pragma`,
monkeypatches, fakes, mocks, skips, or xfails were introduced.
