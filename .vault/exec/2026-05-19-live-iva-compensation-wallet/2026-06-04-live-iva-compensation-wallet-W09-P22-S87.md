---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S87'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]'
  - '[[2026-05-26-live-iva-remote-evidence-reconciliation-adr]]'
---

# Backend Remote-State Reload Bootstrap

Scope: `src/aeat/application/live`, `src/aeat/adapters/persistence/storage`, `.vault/exec`.

## Description

- Reproduced the backend-only reload gap observed after live wallet success: `load_iva_remote_state()` could fail outside the CLI root callback because no active bucket session was open.
- Compared the reload path with `capture_iva_remote_state()`, which already opens a profile storage session around live acquisition.
- Added an application helper that opens the active profile storage session only when an active bucket exists and no session is already active.
- Routed `list_iva_compensation_history()` and `load_iva_remote_state()` through that helper.
- Added a real profile-registration regression test that seeds IVA compensation state, closes the storage session, then calls `load_iva_remote_state()` without CLI bootstrap.
- Added a fail-closed no-active-profile regression so remote IVA reload cannot silently read or create root/default storage.
- Verified the current active-profile backend reload directly with redacted aggregate output only.

## Outcome

Focused gates passed:

- `.venv\Scripts\python.exe -m ruff check src/aeat/application/live/__init__.py src/aeat/application/live/test_iva_wallet_capture_backend.py`
- `.venv\Scripts\python.exe -m pytest -q src/aeat/application/live/test_iva_wallet_capture_backend.py::test_remote_iva_evidence_reload_opens_active_profile_session_without_cli_bootstrap src/aeat/application/live/test_iva_wallet_capture_backend.py::test_remote_iva_evidence_roundtrips_through_profile_secure_sql src/aeat/application/live/test_iva_wallet_capture_backend.py::test_iva_wallet_history_report_surfaces_lots_and_authority_decisions`
- `.venv\Scripts\python.exe -m pytest -q src/aeat/application/live/test_iva_remote_state_acquisition.py::test_remote_state_reload_refuses_without_active_profile src/aeat/application/live/test_iva_wallet_capture_backend.py::test_remote_iva_evidence_reload_opens_active_profile_session_without_cli_bootstrap`

Direct active-profile backend reload, without contacting AEAT and without printing private values, reported:

- 12 IVA compensation history rows.
- 8 carry-forward lots.
- 2 wallet authority decisions.
- 10 stored wallet observations.
- 21 stored acquisition manifests.
- The visible authority decisions for 2026 1T and 2026 2T select `aeat_wallet`, carry `wallet_only` divergence, and are not blocked or stale.

## Notes

This fixes backend reload/bootstrap ergonomics. It does not change live AEAT acquisition and it does not make any AEAT network request.

The earlier no-manifest failure is treated honestly as a storage-session/routing symptom: direct backend callers were relying on CLI bootstrap side effects. The current fix opens the profile storage session at the application reload boundary rather than weakening repository fail-closed behavior or falling back to root storage.

The no-active-profile case now fails closed with a storage readiness error. That is deliberate: remote IVA evidence is profile-bound state and must not be served from root/default storage.

Standing live verification remains open in `S82`, and local file workflow harness coverage remains open in `S83`.
