---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
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

Disposition checkpoint recorded.

Evidence:

- `uv run --no-sync ruff check src/aeat/adapters/outbound/google/_oauth_flow.py src/aeat/adapters/outbound/google/_errors.py src/aeat/adapters/outbound/google/test_package_module_allowlist.py` passed.
- `uv run --no-sync pytest src/aeat/adapters/outbound/google/test_package_module_allowlist.py src/aeat/adapters/outbound/google/test_records.py -q` passed with 21 tests.

## Notes

- No code change was required in `_oauth_flow.py`; the remote-mirror enforcement point is the session-store / sync-push boundary hardened under `W12.P24.S98`.
- The plan checkbox remains open until the shared dirty plan file can be updated without pulling unrelated concurrent edits into this commit.
