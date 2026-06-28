---
tags: ["#exec", "#live-iva-compensation-wallet"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S03"
related:
  - "[[2026-05-19-live-iva-compensation-wallet-plan]]"
---

# `live-iva-compensation-wallet` `W03.P02.S03`

Added an application-level cross-form Modelo 390 test over persisted Modelo 303 observations without duplicating form business formulas in test code.

- Created: `src/aeat/application/calculations/test_binding_prefill.py`
- Modified: `.vault/audit/2026-05-20-live-iva-compensation-wallet-review.md`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

The new test calculates four Modelo 303 periods through the registry from ledger observations, persists the resulting typed observations in `CalculationObservationRepository`, resolves Modelo 390 previous-filing bindings from the encrypted local store, and calculates the annual Modelo 390 snapshot with annual ledger binding values plus those prefilled previous-filing values.

The assertions compare production annual outputs to 303-sourced reconciliation casillas and verify the binding-prefill periods that fed the annual summary. The test uses production registry calculation and binding-prefill functions rather than mirroring Modelo 303 or Modelo 390 formulas.

No live AEAT calls, browser sessions, wallet pulls, form submissions, signing, payment, amendment, or remote mutation paths were run for this step.

The rolling audit records the original coverage gap as `WALLET-041`.

The exact L3 plan row was closed by direct checkbox edit because the current vaultspec step command accepts only duplicate leaf ids such as `S03`.

## Tests

- `uv run pytest src/aeat/application/calculations/test_binding_prefill.py -q` completed with 1 passed.
- `uv run pytest src/aeat/application/calculations/test_binding_prefill.py src/aeat/application/calculations/test_observations_repository_roundtrip.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py -q` completed with 36 passed.
- `uv run ruff check src/aeat/application/calculations/test_binding_prefill.py` passed.
- `git diff --check -- src/aeat/application/calculations/test_binding_prefill.py` passed.
