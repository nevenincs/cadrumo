---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S03'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
---

# `live-iva-compensation-wallet` `W01.P02.S03`

Added opt-in live smoke coverage for the authenticated AEAT IVA compensation wallet reader and application capture chain.

- Created: `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet_live.py`
- Created: `src/aeat/application/live/test_iva_wallet_live.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

The live test is gated by the existing live-read marker and `AEAT_LIVE_TESTS_ENABLED` mechanism. It acquires an operator-approved Cl@ve Movil session for the wallet URL, calls the real read-only wallet adapter, and asserts only structural evidence properties: read mode, Modelo 303 target, source URL, raw hash, row read markers, and total-pending consistency.

The test intentionally does not pin or store any operator tax amounts. A live driver failure is treated as a real failure rather than silently accepting auth-gate or parser errors.

The application-level live test uses the active profile, captures the live wallet through the application service, reloads persisted wallet evidence, loads persisted reconciliation decision history, compares wallet totals to the decision, and exercises the local Modelo 303 wallet guard with the live decision.

The plan row was closed by direct edit because `uv run vault plan step check .vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md W01.P02.S03` could not spawn `vault`.

## Tests

`uv run ruff check` passed for the changed wallet, recurrence, live, and repository files.

`uv run pytest src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet_live.py src/aeat/application/live/test_iva_wallet_live.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/live/test_filed_capture_calculation_history.py src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py src/aeat/application/calculations/test_observations_repository_roundtrip.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_bucket_aggregation_flow.py -q --disable-warnings` completed with 42 passed and 2 live-gated deselected.
