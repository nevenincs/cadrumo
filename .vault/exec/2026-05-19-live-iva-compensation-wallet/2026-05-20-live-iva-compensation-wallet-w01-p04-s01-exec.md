---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S01'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
  - '[[2026-05-19-iva-compensation-chain-plan]]'
---

# `live-iva-compensation-wallet` `W01.P04.S01`

Added an explicit local Modelo 303 IVA compensation recurrence extraction API for reconciliation comparison.

- Modified: `src/aeat/application/calculations/_binding_prefill.py`
- Modified: `src/aeat/application/calculations/_iva_wallet_reconciliation.py`
- Modified: `src/aeat/application/calculations/__init__.py`
- Modified: `src/aeat/application/live/test_filed_capture_calculation_history.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

`extract_modelo_303_local_iva_compensation_recurrence` now projects the local previous-filing binding into a typed comparison record that carries amount, binding id, source modelo, source filing year, source periods, and resolution time. The record is comparison evidence only; it does not select the effective value.

`reconcile_modelo_303_iva_compensation` now consumes that explicit recurrence extraction before applying the wallet/override/local authority ladder. This makes the behavioral boundary visible in code: local recurrence is a cross-check and fallback input to reconciliation, not a direct casilla 110 selector.

The plan row was closed by direct edit because `uv run vault plan step check .vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md W01.P04.S01` could not spawn `vault`.

## Tests

`uv run ruff check` passed for the changed wallet, recurrence, live, and repository files.

`uv run pytest src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet_live.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/live/test_filed_capture_calculation_history.py src/aeat/application/calculations/test_observations_repository_roundtrip.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py -q --disable-warnings` completed with 23 passed and 1 live-gated deselected.
