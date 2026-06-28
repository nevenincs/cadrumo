---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S91'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-03-live-iva-compensation-wallet-code-review-audit]]'
---

# W10.P24.S91 Clave cleanup timeout hardening

Scope: Bound Cl@ve browser cleanup after live IVA remote-state auth timeout.

## Description

- Recorded the failed S56 live retry honestly: no successful live evidence was claimed.
- Added `AEAT_BROWSER_CLOSE_TIMEOUT_MS` to the central `Settings` schema and `env/.env.example`.
- Routed Cl@ve browser context cleanup through a bounded close helper.
- Routed Cl@ve browser-session cleanup through the same centralized timeout.
- Added regression coverage for hanging context and browser-session close coroutines.

## Outcome

- Full Cl@ve provider test module passes with 39 tests.
- Focused settings/env alignment tests pass.
- Ruff passes on the touched auth and config files.

## Notes

This step hardens local browser cleanup after auth timeout. It does not perform live AEAT reads and does not claim live evidence success. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.
