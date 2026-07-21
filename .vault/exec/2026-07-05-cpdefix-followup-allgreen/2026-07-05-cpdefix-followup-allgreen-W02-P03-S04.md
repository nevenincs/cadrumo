---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---

# Prove the current M347 summary route remains invoice-owned and does not falsely promote reserved counterpart sources

## Scope

- `src/aeat/_data/registry/aeat/modelos/347/revisions/2008-y-siguientes/`

## Description

- Run RAG code and vault discovery for M347 invoice-owned summary bindings and reserved counterpart-provider promotion.
- Confirm the current M347 summary binding file declares `collectible_invoice`, not `ledger_transaction` or `purchase_invoice_evidence`.
- Confirm the registry test asserts the two M347 summary bindings are invoice-owned and disjoint from reserved provider sources.
- Confirm the counterpart service test keeps the reserved resolver from claiming invoice-owned M347 registry bindings.
- Run the focused M347 registry and counterpart service gate.

## Outcome

M347 source ownership is current and intentionally invoice-owned:

- `0001-counterpart-summary.toml` declares both summary bindings with `source = "collectible_invoice"`.
- `test_modelo_347_registry_bindings.py` asserts the summary bindings are `BindingSourceKind.COLLECTIBLE_INVOICE` and disjoint from `BindingSourceKind.LEDGER_TRANSACTION` / `BindingSourceKind.PURCHASE_INVOICE_EVIDENCE`.
- `test_per_modelo_service.py` asserts the counterpart resolver returns no binding values, provenance, or transaction ids for the invoice-owned M347 summary route.

Verification passed:

`uv run --no-sync pytest -q -n 0 src/aeat/domain/calculations/registry/tests/test_modelo_347_registry_bindings.py src/aeat/application/aggregation/tests/test_per_modelo_service.py -k "counterpart" --tb=short`

Result: 4 passed, 23 deselected.

No code changes were required.

## Notes

The old "M347 has no bindings" blocker is stale. The current route does not fire the counterpart-provider promotion trigger because it does not declare the reserved sources.
