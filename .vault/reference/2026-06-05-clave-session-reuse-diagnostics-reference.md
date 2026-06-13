---
tags:
  - '#reference'
  - '#clave-session-reuse'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
---

# `clave-session-reuse-diagnostics` reference: `existing implementation surfaces`

This reference records the codebase surfaces audited after the read-only full-range IVA remote-state command failed at Cl@ve approval timeout.

## Session reuse contract

- `aeat.application.auth._sessions.ensure_authenticated_aeat_session` is the central live-auth orchestrator. It probes persisted session state before acquiring the auth lock, probes again after acquiring the lock, and only falls back to fresh provider authentication when persisted reuse is unavailable or invalid.
- `aeat.application.auth._sessions.load_persisted_session` reads encrypted active-bucket/provider session metadata. `PersistedAuthSession.is_expired(now())` treats `now >= idle_deadline` as expired.
- `aeat.adapters.outbound.aeat.auth._clave_movil.ClaveMovilAuthProvider.probe_persisted_session` is intentionally side-effect free: it must not dispatch a fresh Cl@ve request, must not delete stored session state, and must verify the stored landing/default authenticated page rather than an explicit selector target.

## Operator diagnostics

- `aeat.application.auth._operator.test_operator_auth` performs two separate local probes: persisted session presence/expiry and provider configuration health.
- For Cl@ve Móvil, provider `probe_result="ok"` only means the configured DNI/NIE classifies as a usable Cl@ve identity. It does not prove that the encrypted AEAT browser session is reusable.
- `aeat.application.auth._operator.build_live_auth_preflight_report` is the live-read preflight source rendered before any AEAT phone approval wait.

## S100 diagnostic hardening

- The live IVA CLI now renders `auth_persisted_session_state` independently from `auth_probe_result`.
- Expected states are `no_provider`, `no_session`, `expired`, `live`, or `unknown`.
- A live run showing `auth_probe_result=ok` and `auth_persisted_session_state=expired` means the Cl@ve configuration is locally healthy but the command must perform fresh Cl@ve authentication before any AEAT read-only acquisition can proceed.
