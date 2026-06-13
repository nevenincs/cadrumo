---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S90'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-03-live-iva-compensation-wallet-code-review-audit]]'
---

# W09.P23.S90 Modelo 100 payments-retentions registry expectation repair

Scope: Resolve the Modelo 100 payments-retentions construct expectation drift found during S88 registry verification.

## Description

- Reproduced the failing payments/retentions binding assertion in `test_modelo_100_registry.py`.
- Confirmed the registry construct TOML is coherent: prior-year base-liquidation negative carry-forward is owned by the Anexo C construct, not by payments/retentions.
- Replaced the over-broad string-filter expectation with dependency-classification-based expected binding and relation sets.
- Added an explicit assertion that the base-negative carry-forward binding remains excluded from payments/retentions and present in the Anexo C carry-forward construct.
- Updated the live IVA wallet audit item WALLET-054 from open to reviewed and resolved.

## Outcome

- Focused payments/retentions registry tests pass.
- The full Modelo 100 registry test module passes with 35 tests.
- Ruff passes for the edited registry test file.

## Notes

No registry TOML was changed for this step. No live AEAT request was made. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.
