---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S55'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W04.P10.S55 Read-Back Docs And Reference Gates

Scope: verify docs, locale/help, and reference gates for W04 read-back surfaces.

## Description

- Verified `docs/how-to/reconcile.md` teaches `aeat app modelo reconcile history`.
- Verified IVA wallet correction examples exist in Modelo 390 and calculation-value guides.
- Ran documented-command conformance and CLI-reference drift.
- Fixed an import cycle in `aeat.application.modelo._verification_actions` that blocked CLI reference generation by importing the IVA wallet blocked-message helper directly from `_iva_wallet_gate`.

## Outcome

S55 is closed. W04 docs and generated CLI reference are synchronized, and the docs generator import path is healthy.

## Notes

- Checks run: documented-command conformance, CLI-reference drift, live help probes for `m036 list`, `reconcile history`, and `iva-wallet correct`, plus ruff and import checks for `_verification_actions`.
