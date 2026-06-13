---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# W04.F01 Modelo readiness and ledger preflight convergence

## Scope

- Follow-up: `W04.F01`
- Goal: prevent Modelo 303 readiness from reporting ready, and calculation from producing a zero draft, while same-period ledger preflight has blocking issues.

## Changes

- Extended the canonical operator state projection with combined Modelo readiness:
  - profile readiness,
  - ledger preflight requirement,
  - ledger readiness,
  - ledger period,
  - ledger checked count,
  - ledger issue records.
- Modelo readiness CLI now renders the ledger readiness fields and individual ledger issues.
- Ledger-backed Modelo calculation now runs ledger preflight before registry evaluation and refuses when active period ledger rows are incomplete.
- Bucket-aggregation tests now mark valid IVA ledger rows with a category and add a regression proving missing-category rows block calculation before a draft revision is persisted.

## Verification

- `uv run pytest src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/test_state_projection.py::test_modelo_303_readiness_includes_ledger_preflight_blockers -q`
- `uv run pytest src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/test_state_projection.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_export.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py -q`
- `uv run ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/state_projection.py src/aeat/application/test_state_projection.py src/aeat/entrypoints/cli/_modelo.py`
- Disposable CLI probe: Modelo 303 readiness reported `ready False` and `ledger_ready False` for an active Q1 transaction missing `category_id`; Modelo calculation refused with `ledger preflight blocks modelo calculation`.
