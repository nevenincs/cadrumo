---
tags:
  - '#exec'
  - '#google-oauth'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S05+S13'
related:
  - "[[2026-05-13-google-oauth-plan]]"
  - "[[2026-05-08-google-oauth-adr]]"
---

# `google-oauth` `W01.P01.S05+S13`

OAuth Desktop login flow. Loopback IP + PKCE consent flow via `InstalledAppFlow.run_local_server(port=0)`, plus the unsecured-mode safety check that refuses OAuth attempts when the secret store backend is `unsecured` AND the active profile carries a real Spanish NIF / NIE / CIF.

- Created: `src/aeat/adapters/outbound/google/_oauth_flow.py` — `check_unsecured_mode_safety`, `resolve_active_tax_id`, `credentials_to_records`, `run_login_flow`
- Created: `src/aeat/adapters/outbound/google/test_oauth_flow.py` — 11 unit tests
- Modified: `pyproject.toml` — added `src/aeat/adapters/outbound/google/test_*.py` to `[tool.ruff.lint.per-file-ignores]` for S105/S106/S101/T20 (false positives on synthetic OAuth fixtures)

## Description

The flow is structured as four small, separately testable units:

- `check_unsecured_mode_safety(profile, tax_id)` — pure guard. Reads `aeat_secret_store_backend` from settings; if it's `unsecured`, calls `looks_like_real_tax_id(tax_id)` (the canonical canary used by the secret-store master-key boundary). Refuses with `GoogleAuthUnsecuredModeRefusedError` carrying `context={profile, backend}` and `suggestion="set aeat_secret_store_backend=keyring..."`.
- `resolve_active_tax_id(profile)` — looks up the profile's bucket pointer in workflow state, loads the secure profile bucket, returns `record.values.get("tax.id", "")`. Returns empty string when profile or record is absent.
- `credentials_to_records(refresh_token, token_uri, account_email, granted_scopes, issued_at)` — pure mapping. Refuses partial-grant scope sets (must include both `drive.file` AND `spreadsheets`) with `GoogleAuthScopeInsufficientError`, then constructs the strict pydantic `OAuthToken` + `OAuthMetadata` records.
- `run_login_flow(client, profile, *, flow_runner=None, clock=None)` — orchestrator. Executes safety check → resolves tax id → invokes the runner → maps to records. The `flow_runner` and `clock` parameters are test seams; defaults are `_real_run_local_server` (lazy-imports `google_auth_oauthlib`) and `datetime.now(UTC)`.

The `_real_run_local_server` runner translates upstream exceptions into the typed `GoogleAuthError` hierarchy:

- `OSError` from port-binding → `GoogleAuthLoopbackBindError`
- bare `Exception` mentioning "browser" → `GoogleAuthBrowserOpenError`
- bare `Exception` mentioning "transport"/"connect"/"network" → `GoogleAuthNetworkError`
- `ValueError` from `from_client_config` → `GoogleAuthNetworkError`
- `ImportError` of `google_auth_oauthlib` → `GoogleAuthNetworkError` with `suggestion="uv sync"`

`account_email` is extracted from the credential's `id_token_email` attribute when present, falling back to a best-effort decode of the credential's `id_token` JWT via `google.oauth2.id_token.verify_oauth2_token`.

## Tests

- `pytest src/aeat/adapters/outbound/google/ -q` — 39 passed (11 oauth_flow + 9 profile_binding + 19 records).
- `ruff check src/aeat/adapters/outbound/google/_oauth_flow.py src/aeat/adapters/outbound/google/test_oauth_flow.py` — clean.
- Coverage: round-trip through credentials_to_records, partial-grant refusal (drive.file missing AND sheets missing both tested), empty-account-email pydantic refusal, unsecured-mode passes for keyring/empty-tax-id/synthetic-NIF, refuses for real NIF, runner skipped when safety refuses, scope-insufficient propagates from runner, success path through injected runner + clock seams.

## Outstanding (subsequent commits)

- `_refresh.py` (S08+S09+S12) — lazy refresh + invalid_grant detection + 7d Testing-project warning
- `_config/_google.py` (S04+S06+S07+S02) — CLI commands wired to the flow
- Live-gated tests (S15)
- Forbidden-import test (S18)
- Spanish CLI i18n strings
- Re-add `aeat.adapters.outbound.google` to import-contract smoke test
