---
tags: ["#exec", "#live-iva-compensation-wallet"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S03"
related:
  - "[[2026-05-19-live-iva-compensation-wallet-plan]]"
---

# `live-iva-compensation-wallet` `W03.P01.S03`

Added traceable Modelo 303 calculation coverage from ledger rows through registry outputs for positive, negative, zero, and compensation-applied periods.

- Modified: `src/aeat/application/modelo/test_bucket_aggregation_flow.py`
- Modified: `.vault/audit/2026-05-20-live-iva-compensation-wallet-review.md`

## Description

The new test seeds real bucket-local ledger rows across all four quarters and calculates each period through `calculate_modelo_revision_from_bucket_aggregation`. It verifies the provenance chain for every revision and asserts period outcome shape without reimplementing the registry formulas.

Covered period shapes:

- Positive result: `iva.resultado-regimen-general` and `iva.resultado` are positive, with no generated compensation.
- Negative result: `iva.resultado-regimen-general` and `iva.resultado` are negative, and generated compensation is positive.
- Zero result: regime result, final result, and generated compensation are all zero.
- Compensation-applied result: a persisted non-blocking wallet decision reduces the final result and produces a positive applied-compensation casilla.

The compensation-applied scenario keeps the Modelo 303 taxpayer/profile guard active by writing a matching profile identity in the test-local bucket storage.

The rolling audit records the original coverage gap as `WALLET-038`.

The exact L3 plan row was closed by direct checkbox edit because the current vaultspec step command accepts only duplicate leaf ids such as `S03`.

## Tests

- `uv run pytest src/aeat/application/modelo/test_bucket_aggregation_flow.py -q` completed with 5 passed.
- `uv run pytest src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py -q` completed with 59 passed.
- `uv run ruff check src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py` passed.
- `git diff --check -- src/aeat/application/modelo/test_bucket_aggregation_flow.py` passed.
