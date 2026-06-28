---
tags: ["#exec", "#live-iva-compensation-wallet"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S02"
related:
  - "[[2026-05-19-live-iva-compensation-wallet-plan]]"
---

# `live-iva-compensation-wallet` `W03.P01.S02`

Verified and hardened the Modelo 303 periodic bucket-aggregation test so it proves registry-backed binding and formula provenance rather than mirrored arithmetic.

- Modified: `src/aeat/application/modelo/test_bucket_aggregation_flow.py`
- Modified: `.vault/audit/2026-05-20-live-iva-compensation-wallet-review.md`

## Description

The production calculation path already resolves bucket ledger values through `resolve_modelo_ledger_binding_values_from_repositories`, maps available binding values to bound casilla inputs, and runs `calculate_registry_snapshot` for the Modelo 303 revision.

The test coverage now checks the important provenance contract directly. Bound ledger casillas must be persisted as typed `CasillaObservation` rows with no formula id and non-empty legal/source refs. Computed Modelo 303 casillas must carry the registry formula id, operand refs, legal refs, and source refs. This confirms the calculation revision is consuming ledger observations and registry formulas rather than a parallel application arithmetic path.

The rolling audit records the original test gap as `WALLET-037`.

As with W03.P01.S01, the exact L3 row was closed by direct checkbox edit because `vaultspec-core vault plan step check` accepts only duplicate leaf ids such as `S02`, not the full `W03.P01.S02` display path.

## Tests

- `uv run pytest src/aeat/application/modelo/test_bucket_aggregation_flow.py -q` completed with 4 passed.
- `uv run pytest src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py -q` completed with 35 passed.
- `uv run ruff check src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py` passed.
- `git diff --check -- src/aeat/application/modelo/test_bucket_aggregation_flow.py` passed.
