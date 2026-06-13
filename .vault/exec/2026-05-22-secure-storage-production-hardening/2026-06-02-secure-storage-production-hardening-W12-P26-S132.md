---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S132'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-W12-P24-S98]]'
---

# `secure-storage-production-hardening` `W12.P26.S132`

## Description

- Reviewed `src/aeat/adapters/outbound/google/_oauth_flow.py` against the `AFR-030` signals.
- Confirmed the OAuth flow uses centralized settings through `load_settings()` and does not read naked environment variables.
- Confirmed Google OAuth exceptions derive from the core `AeatError` hierarchy through `GoogleAuthError`.
- Confirmed user-facing remediation suggestions and translated failure messages use `tr()`/locale keys where the flow surfaces operator guidance.
- Confirmed the flow does not persist OAuth client/token/metadata records itself; it returns strict `OAuthToken` and `OAuthMetadata` pydantic records to the CLI/session-store layer that is mirrored under `W12.P24.S98`.
- Confirmed the manifest-bucket read in `resolve_active_tax_id()` is read-only profile discovery for unsecured-mode refusal, not an alternate persistence backend.

## Outcome

Closed.

Evidence:

- `uv run --no-sync ruff check src/aeat/adapters/outbound/google/_oauth_flow.py src/aeat/adapters/outbound/google/_errors.py src/aeat/adapters/outbound/google/test_package_module_allowlist.py` passed.
- `uv run --no-sync pytest src/aeat/adapters/outbound/google/test_package_module_allowlist.py src/aeat/adapters/outbound/google/test_records.py -q` passed with 21 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/google/test_records.py src/aeat/adapters/outbound/google/test_package_module_allowlist.py src/aeat/entrypoints/cli/_config/test_google_error_localisation.py` passed with 24 tests on 2026-06-03.
- `uv run --no-sync ruff check src/aeat/adapters/outbound/google/_oauth_flow.py src/aeat/adapters/outbound/google/_errors.py src/aeat/adapters/outbound/google/test_records.py src/aeat/adapters/outbound/google/test_package_module_allowlist.py src/aeat/entrypoints/cli/_config/test_google_error_localisation.py` passed on 2026-06-03.

## Notes

- The earlier no-code-change conclusion was too narrow. `_run_local_server()` could re-raise unclassified upstream OAuth failures outside the `GoogleAuthError` hierarchy caught by the CLI. `_raise_local_server_error()` now wraps the fallthrough as `GoogleAuthNetworkError` with the original exception preserved as cause, and `test_oauth_flow.py` covers browser, network, and unclassified translation paths.
- Follow-up review also found `resolve_active_tax_id()` degraded missing active-profile bucket/record state to an empty tax id. That could bypass unsecured-mode refusal and proceed toward loopback OAuth. Missing profile state now raises `GoogleAuthProfileUnboundError` with a localized message and `tr()`-resolved repair guidance before `_run_local_server()` is reached.
- The plan checkbox was closed on 2026-06-03 after the shared plan file stabilised for this row. The live OAuth browser consent probe remains opt-in live evidence and was not counted as the offline ledger closure.
