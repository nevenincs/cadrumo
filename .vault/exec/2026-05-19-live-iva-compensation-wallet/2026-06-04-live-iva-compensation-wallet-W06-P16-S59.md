---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S59'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-03-live-iva-compensation-wallet-code-review-audit]]'
---

# `live-iva-compensation-wallet` `W06.P16.S59`

## Scope

Centralized read-only browser-action constants for Clave, Pre303, and wallet navigation.

## Description

- Removed the local Clave own-name representation action string and consumed the TOML-backed Pre303 action label through `Settings.external_constants()`.
- Kept wallet and auth action allow-lists under centralized live-safety constants.
- Verified new unclassified AEAT browser actions fail the explicit allow-list guard.

## Outcome

Passing verification:

- Full W06.P16 guard files -> 163 passed.
- Focused ruff on touched guard/auth files -> passed.

## Notes

This step did not inventory every AEAT/Sede literal in the repository; that broader mandate remains separately tracked in W09.P21.
