---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# W03.P04.S01 persisted IVA wallet decision gate

## Scope

- Step: `W03.P04.S01`
- Goal: require persisted non-blocking reconciliation decisions before AEAT remote-state values can affect Modelo 303 outputs.

## Changes

- Hardened `calculate_modelo_revision` so a supplied `iva_compensation_decision` is only accepted when the same decision is already present in `IvaWalletDecisionRepository` for the work-unit taxpayer, filing year, and period.
- Preserved the existing no-argument replay path: Modelo 303 calculation still loads the persisted decision automatically when the caller does not provide one.
- Added an injectable real `IvaWalletDecisionRepository` to the calculation and bucket-aggregation surfaces so secure SQL-backed tests can persist and verify decisions without fakes or monkeypatching.
- Added a regression test proving that `persist=False` reconciliation decisions cannot feed the Modelo 303 engine and do not persist a draft revision.
- Updated the bucket-aggregation compensation scenario to save the decision into the encrypted decision repository before calculation.

## Verification

- `uv run pytest src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py -q`
- `uv run ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_bucket_aggregation_flow.py`
