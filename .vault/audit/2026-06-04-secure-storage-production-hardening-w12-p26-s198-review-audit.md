---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S198]]'
---

# `secure-storage-production-hardening` `W12.P26.S198` Review

## S198-001 | FIXED | Operator auth clear failed after profile storage session closed

`src/aeat/application/auth/_operator.py` cleared persisted sessions inside an
active-profile storage span, but then loaded and updated workflow state after
that span had closed. In the production-shaped state where the active-profile
pointer exists but the per-process bucket session is closed, the workflow
repository refused with `StorageValidationError` before the operator could clear
the configured auth provider.

The fix routes the workflow-state load/update through `_active_profile_storage_span()`
using the resolved settings, so the service reopens the selected profile storage
session before touching encrypted workflow state.

## S198-002 | FIXED | Login audit event now shares the auth-session storage envelope

`login_operator_auth()` already performed live session acquisition inside an
active-profile storage span, but appended the `auth.session.verified` workflow
event after that span. The workflow update now occurs inside the same
active-profile storage context as the remote-provider session acquisition.

## S198-003 | PASS | Existing active sessions are reused

The storage-span helper now reuses an already-active bucket session instead of
opening a nested session. This preserves profile-create/test contexts where the
session is already unlocked and avoids requiring a reusable bucket manifest
before bootstrap enrollment is complete.

## S198-004 | PASS | Local session probe degradation is logged, not silent

The local persisted-session probe treats `AeatError` and `OSError` as an absent
local session only after logging a debug record with `exc_info=True`. That is an
acceptable non-critical probe degradation: login and clear mutations still raise
their storage failures, while `auth test` avoids failing the whole readiness
report on a missing/unreadable local session token.

No `noqa`, `pragma`, skips, xfails, mocks, fakes, stubs, or raw user-facing
strings were introduced. Existing auth operator errors remain `AeatError`
subclasses and localized through `tr()` / `translated_message`.

## S198-005 | FIXED | Live-auth preflight honours explicit Settings

`build_live_auth_preflight_report(settings=...)` used the supplied settings for
redacted certificate/Cl@ve fields, but delegated status and provider probing to
`test_operator_auth()` which reloaded process settings. A certificate path
supplied through the centralized `Settings` object could therefore render as
configured while the probe still reported the ambient process certificate state.

The fix threads `Settings` through `test_operator_auth()`,
`_probe_local_session()`, `_probe_configured_provider()`,
`_probe_certificate_bundle()`, and `_probe_clave_movil_identity()`, so the
preflight shape and the probe verdict share the same settings source.

Validation:

- `uv run --no-sync pytest src/aeat/application/auth/test_operator.py src/aeat/entrypoints/cli/_config/test_auth_round5_surface.py -q` passed with 35 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync pytest -q src/aeat/application/auth/test_operator_storage_session.py src/aeat/application/auth/test_operator.py` passed with 26 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync ruff check src/aeat/application/auth/_operator.py src/aeat/application/auth/test_operator_storage_session.py src/aeat/application/auth/test_operator.py src/aeat/entrypoints/cli/_config/test_auth_round5_surface.py` passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: subagent review remains unavailable because the reviewer agent hit
the account usage limit earlier in this run. Host review found no remaining
critical, high, medium, or low findings in the S198 slice.

Disposition: close `AFR-096`.
