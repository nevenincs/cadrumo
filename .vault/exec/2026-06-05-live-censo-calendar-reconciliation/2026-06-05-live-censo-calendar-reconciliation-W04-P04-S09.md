---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S09'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# `live-censo-calendar-reconciliation` `W04.P04.S09` exec - fresh profile password unlock

## Scope

Step `W04.P04.S09` - Unlock profile-bound live storage with a non-interactive secret-store passphrase or keychain session; `env/.env`.

## Description

- Corrected the live verification model: a live user test must not depend on unlocking a stale shared active profile. It must create a fresh profile with an operator-owned passphrase.
- Created an isolated live-user smoke root under `var/live-user-smoke/20260611-1248`, overriding `AEAT_LOCAL_STORAGE_ROOT`, `AEAT_SECRET_STORE_DIR`, `AEAT_BLOB_STORE_DIR`, and `AEAT_AUDIT_DIR` so the shared worktree profile registry was not mutated.
- Forced `AEAT_SECRET_STORE_BACKEND=file` and supplied a fresh throwaway passphrase only as a transient process environment value.
- Created profile `live-user-smoke-20260611-1248` with the live Cl@ve NIE from `env/.env`, activity facts, general IVA regime, and Madrid tax-residence facts.
- Verified the same passphrase-backed profile can be switched into, read by `config profile status`, and used by the overview calendar.
- Retained the negative observations: the operator-provided short candidate is below the passphrase length policy, and the central dev-test database password is only for isolated test storage; neither is the password for the stale shared active profile.

## Outcome

- `uv run aeat --format json config profile create live-user-smoke-20260611-1248 --quiet --accept-defaults ...` succeeded and made the new profile active.
- `uv run aeat --format json config switch live-user-smoke-20260611-1248` succeeded.
- `uv run aeat --format json config profile status` succeeded with `tax_id_present=true`, `activity_present=true`, `iva_regime=GENERAL`, and `tax_residence_ccaa=madrid`.
- `uv run aeat --format json app overview calendar --from 2026-01-01 --to 2026-12-31 --allow-incomplete` succeeded and returned obligation rows for Modelos 100, 303, 390, and 721. Each filing row required justificante verification and showed `aeat_submission_state=not_observed` before live evidence was captured.
- `uv run aeat --format json app live notifications list`, `app live expedientes list`, and `app live justificante list` all succeeded against the fresh profile with zero persisted snapshots.
- `uv run aeat --format json app live filed list --modelo 303 --from-year 2026 --to-year 2026` reached the live Cl@ve Móvil route with matching profile/auth identity, then timed out waiting for mobile completion.
- `uv run aeat --format json config profile censo pull` reached the same live Cl@ve Móvil route and timed out waiting for mobile completion.

## Notes

- `W04.P04.S09` is now checked because the fresh live-user profile/password path is proven.
- `W04.P04.S10` and `W04.P04.S11` remain open: authenticated censo/filed-history/message/justificante pulls did not complete because Cl@ve Móvil authentication timed out after the configured 120 second maximum.
- The failed live auth diagnostics reported `auth_route=clave_movil_non_qr_request`, `identity_alignment=matches`, `identity_kind=NIE`, `verification_code_present=true`, and `failure_mode=auth_completion_timeout`.
