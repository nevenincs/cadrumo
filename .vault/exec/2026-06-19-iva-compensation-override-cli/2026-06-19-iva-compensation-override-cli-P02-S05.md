---
tags:
  - '#exec'
  - '#iva-compensation-override-cli'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:e20d616977723d4a156ba60b851443e9613c3b5de06d648ae6d6f9289d7de16d'
step_id: 'S05'
related:
  - "[[2026-06-19-iva-compensation-override-cli-plan]]"
---

# Add the IvaWalletOverrideResult output schema and register it for JSON-schema conformance

## Scope

- `src/aeat/entrypoints/cli/_modelo_payloads.py`

## Description

- Add the `IvaWalletOverrideResult` output schema carrying operation, filing year, period, taxpayer NIF, amount, reason, evidence locator, selected authority, and divergence.
- Register the schema for JSON-schema conformance under the `modelo.iva_wallet.override` command identifier.

## Outcome

- The override verb emits a registered, typed envelope with the mandatory provenance fields; the JSON-schema conformance gate passes for the new command.
- The result documents that the override unblocks the carry calculation only, not the dependent-period official-evidence verify gate.
- The envelope carries the shared spine and no bespoke advisory field, per the notice-channel discipline.

## Notes

- The schema was present at HEAD; this Step verified it against the conformance gate and closed it with an execution record.
