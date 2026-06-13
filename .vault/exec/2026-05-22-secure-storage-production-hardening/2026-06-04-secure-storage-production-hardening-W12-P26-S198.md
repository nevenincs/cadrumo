---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S198'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s198-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S198`

Closed `AFR-096` for operator auth.

## Description

- Reviewed `src/aeat/application/auth/_operator.py` against the
  `remote-mirror` classification: secure-object workflow state,
  active-profile storage, manifest-bucket session handling, and
  remote-provider auth acquisition.
- Reproduced the adverse production state where the active-profile pointer
  remains selected after the bucket storage session closes.
- Fixed `clear_operator_auth()` so workflow-state reads and writes run inside
  `_active_profile_storage_span(resolved_settings)`.
- Fixed `login_operator_auth()` so the `auth.session.verified` workflow update
  shares the same active-profile storage context as session acquisition.
- Hardened `_active_profile_storage_span()` to merge partial explicit settings,
  reuse existing active bucket sessions, and reopen storage only when no session
  is active.
- Verified the local persisted-session probe degrades only with a debug
  `exc_info=True` record; mutating login/clear storage failures still surface.
- Threaded explicit `Settings` through live-auth preflight status, local-session,
  certificate, and Cl@ve probes so centralized settings drive the whole report.
- Added real-behavior regression coverage for clearing operator auth after the
  profile-create storage span has closed.
- Added real-behavior preflight coverage for an explicit certificate path supplied
  via `Settings` while the ambient process settings carry no certificate path.

## Outcome

`AFR-096` is closed. Operator auth now handles the active-pointer /
closed-session adverse state without falling through to a low-level
`StorageValidationError`, and the live-login workflow audit event remains scoped
to the same active-profile storage envelope as the remote-provider session
operation.

Validation passed:

- `uv run --no-sync pytest src/aeat/application/auth/test_operator.py src/aeat/entrypoints/cli/_config/test_auth_round5_surface.py -q`
- `$env:PYTHONPATH='src'; uv run --no-sync pytest -q src/aeat/application/auth/test_operator_storage_session.py src/aeat/application/auth/test_operator.py`
- `$env:PYTHONPATH='src'; uv run --no-sync ruff check src/aeat/application/auth/_operator.py src/aeat/application/auth/test_operator_storage_session.py src/aeat/application/auth/test_operator.py src/aeat/entrypoints/cli/_config/test_auth_round5_surface.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No new direct secure-object repository construction, naked environment access,
silent exception swallowing, raw user-facing strings, `noqa`, `pragma`,
monkeypatches, fakes, mocks, skips, or xfails were introduced.
