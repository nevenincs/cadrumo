---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# W03.P04.S03 blocked wallet reconciliation workflow/export surfacing

## Scope

- Step: `W03.P04.S03`
- Goal: surface blocked Modelo 303 IVA wallet reconciliation before calculation/export paths can proceed.

## Changes

- Verification now emits a blocking finding when the latest persisted IVA wallet reconciliation decision for a Modelo 303 work unit is blocked.
- Export now refuses a Modelo 303 revision before draft build or file write when the latest persisted wallet decision is blocked.
- The CLI export verb catches `ModeloIvaWalletReconciliationBlocked` and surfaces the refusal in the command response.
- Added an export regression test proving no output file is written when a verified Modelo 303 revision has a later blocked wallet decision.

## Verification

- `uv run pytest src/aeat/application/modelo/test_export.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py -q`
- `uv run ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_export.py src/aeat/application/modelo/test_export.py src/aeat/entrypoints/cli/_modelo.py`
- `git diff --check -- src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_export.py src/aeat/application/modelo/test_export.py src/aeat/entrypoints/cli/_modelo.py src/aeat/application/calculations/_iva_wallet_reconciliation.py src/aeat/application/calculations/__init__.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_bucket_aggregation_flow.py .vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md .vault/audit/2026-05-20-live-iva-compensation-wallet-review.md .vault/exec/2026-05-19-live-iva-compensation-wallet/2026-05-21-live-iva-compensation-wallet-w03-p04-s01.md .vault/exec/2026-05-19-live-iva-compensation-wallet/2026-05-21-live-iva-compensation-wallet-w03-p04-s02.md`
