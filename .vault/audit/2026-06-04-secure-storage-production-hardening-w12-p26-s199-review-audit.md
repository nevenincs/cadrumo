---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S199]]'
---

# `secure-storage-production-hardening` `W12.P26.S199` Review

## S199-001 | FIXED | Auth session state no longer derives plaintext token paths

`storage_state_paths()` previously composed `Settings.aeat_token_dir` with the
active profile and provider stem. That left the application-level auth-session
identifier tied to a plaintext filesystem directory even though the concrete
session store now persists encrypted secure objects.

The fix routes session identity through `aeat_auth_session_storage_state_path()`,
which returns a stable logical key under `.aeat/auth/sessions/`. The `settings`
parameter is retained for API compatibility, but the encrypted object identity is
active-bucket/provider scoped and does not drift with `aeat_token_dir`.

## S199-002 | PASS | Active-profile and provider partitioning remain explicit

The storage-state tests now pin certificate, Cl@ve Móvil, default-provider, and
active-profile switching behavior against logical keys. They also assert that two
different `aeat_token_dir` values produce the same encrypted object key.

The certificate authenticator and Cl@ve Móvil provider now call the same core
helper, so provider save/resume paths and application session probes cannot drift
apart.

Cross-commit note: the dirty Cl@ve Móvil provider/test files also contained
representation-action centralization through external constants and typed
initial selector-navigation timeout coverage. Those hunks were validated and
kept with the provider-side S199 alignment rather than reverted.

## S199-003 | PASS | Convention and exception hygiene

No new exceptions, broad exception handlers, monkeypatches, fakes, mocks, skips,
xfails, raw user-facing strings, or naked environment access were introduced.
Locale work was not required.

## S199-004 | HONEST DEBT | Existing provider-orchestration tests still use stand-ins

`src/aeat/application/auth/test_ensure_session.py` still contains an inherited
duck-typed provider stand-in and pyright/pyrefly ignore comments. This S199
slice did not expand that debt. It remains outside the storage-key fix and
should be retired under a separate auth-provider protocol narrowing step.

Validation:

- `$env:PYTHONPATH='src'; uv run --no-sync ruff check src/aeat/core/auth_session_keys.py src/aeat/application/auth/_sessions.py src/aeat/application/auth/test_sessions_storage_state_paths.py src/aeat/application/auth/test_persisted_session_metadata.py src/aeat/adapters/outbound/aeat/auth/_authenticator.py src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/adapters/outbound/aeat/auth/test_authenticator.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil_live.py` passed.
- `$env:PYTHONPATH='src'; uv run --no-sync pytest -q src/aeat/application/auth/test_operator.py src/aeat/application/auth/test_operator_storage_session.py src/aeat/application/auth/test_sessions_storage_state_paths.py src/aeat/application/auth/test_persisted_session_metadata.py` passed with 33 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/auth/test_session_store_roundtrip.py src/aeat/adapters/outbound/aeat/auth/test_authenticator.py::test_authenticate_falls_back_after_stale_persisted_session src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py::TestProbePersistedSession::test_probe_uses_existing_encrypted_session_without_invalidating_on_failure` passed with 3 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py::test_auth_browser_action_policy_allows_configured_own_name_representation_action src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py::test_auth_browser_action_policy_rejects_unclassified_representation_action src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py::TestAuthenticateFresh::test_initial_selector_navigation_timeout_is_typed` passed with 3 tests.

Reviewer note: subagent review remains unavailable because the reviewer agent hit
the account usage limit earlier in this run. Host review found no remaining
critical, high, medium, or low findings in the S199 slice.

Disposition: close `AFR-097`.
