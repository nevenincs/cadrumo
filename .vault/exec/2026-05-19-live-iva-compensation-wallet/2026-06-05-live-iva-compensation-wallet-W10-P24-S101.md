---
tags: ['#exec', '#live-iva-compensation-wallet']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S101'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-05-clave-session-reuse-diagnostics-reference]]'
---


# W10.P24.S101 fresh Clave auth reliability

Scope: Wave W10, Phase P24, Step S101.

## Description

- Resolve fresh Cl@ve Móvil live-auth acquisition when no reusable persisted AEAT session exists.
- Seed a reusable session so S100 full-range IVA remote-state capture can be live-verified.

## Outcome

The previous failed diagnostic `20260605T084306Z` was recorded as `app_did_not_prompt` based on operator testimony.

A new fresh auth attempt was run with `uv run --no-sync aeat config auth login --provider clave_movil`. The command failed with `auth_completion_timeout` after reaching AEAT's non-QR Cl@ve route and producing a verification code. The diagnostic id is `20260605T085442Z`. The CLI reported matching identity alignment, NIE identity kind, configured support number, headless browser mode, and `timeout_ms=120000`.

Phone/app state for diagnostic `20260605T085442Z` was later recorded as `operator_did_not_check`.

A subsequent fresh login attempt succeeded with `authenticated=True`, `reused_persisted_session=False`, acquired the auth lock, and seeded a reusable session. The immediately following S100 full-range read-only IVA capture reused that persisted session successfully.

S101 is closed.

No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.
