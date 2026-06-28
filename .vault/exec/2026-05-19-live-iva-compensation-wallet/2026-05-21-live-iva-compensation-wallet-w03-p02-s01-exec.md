---
tags: ["#exec", "#live-iva-compensation-wallet"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S01"
related:
  - "[[2026-05-19-live-iva-compensation-wallet-plan]]"
---

# `live-iva-compensation-wallet` `W03.P02.S01`

Verified Modelo 390 annual IVA reconciliation against four Modelo 303 periods, including annual compensation casillas `97` and `662`.

- Modified: `src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_390_registry.py`
- Modified: `src/aeat/application/modelo/test_bucket_aggregation_flow.py`
- Modified: `.vault/audit/2026-05-20-live-iva-compensation-wallet-review.md`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

The annual Modelo 390 test now drives four Modelo 303 quarterly calculations from ledger observations, including negative periods that generate compensation. It then calculates the annual Modelo 390 snapshot from annual ledger observations plus the generated 303 observations.

The assertions verify that annual ledger-derived totals reconcile with the 303-sourced annual totals, casilla `97` is sourced from the fourth-quarter `iva.compensacion-disponible-fin-periodo`, and casilla `662` is sourced from the non-fourth-quarter `iva.compensacion-generada-periodo` observations. The test reads expected compensation values from produced 303 observations and does not hard-code a duplicate Modelo 390 formula.

The focused validation also exposed two stale test contracts: the Modelo 390 title assertion now matches the committed accented registry title, and the bucket aggregation workflow test now distinguishes work-unit creation events from calculation-created events.

No live AEAT calls, browser sessions, wallet pulls, form submissions, signing, payment, amendment, or remote mutation paths were run for this step.

The rolling audit records the original coverage gap as `WALLET-039`.

The exact L3 plan row was closed by direct checkbox edit because the current vaultspec step command accepts only duplicate leaf ids such as `S01`.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py -q` completed with 18 passed.
- `uv run pytest src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py src/aeat/core/test_external_constants.py -q` completed with 55 passed.
- `uv run pytest src/aeat/application/modelo/test_bucket_aggregation_flow.py -q` completed with 5 passed.
- `uv run ruff check src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py src/aeat/core/test_external_constants.py` passed.
- `git diff --check -- src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py src/aeat/core/test_external_constants.py` passed.
