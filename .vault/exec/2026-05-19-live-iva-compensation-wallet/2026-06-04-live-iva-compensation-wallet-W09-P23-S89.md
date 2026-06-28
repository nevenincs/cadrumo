---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S89'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-03-live-iva-compensation-wallet-code-review-audit]]'
---

# W09.P23.S89 locale audit repair

Scope: Repair live-notification snapshot translation drift through the supported locale CLI.

## Description

- Set concrete `application.live.notifications.errors.*` values for `en`, `es`, `ca`, and `hu` with `python -m aeat.locales set`.
- Preserved the supported locale set of English, Spanish, Catalan, and Hungarian.
- Avoided placeholder/self-reference values for operator-facing notification snapshot errors.

## Outcome

- `python -m aeat.locales audit` reports `ok` for all four supported locale files.
- Locale parity and locale CLI tests pass.

## Notes

This was a local catalogue repair only. No live AEAT request was made. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.
