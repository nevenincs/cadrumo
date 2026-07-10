---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-06'
modified: '2026-07-08'
step_id: 'S281'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Implement Modelo 303 cash-accounting IVA axis

## Scope

- `src/aeat/application/aggregation/_iva_ledger.py`

## Description

- Ground the implementation against the accepted cash-accounting ADR and RAG code/vault searches.
- Add an independent IVA cash-accounting treatment axis instead of extending `IvaCategory`.
- Carry cash-accounting evidence from `Transaction` through IVA ledger observations and binding selectors.
- Add legal catalogue refs for LIVA art. 75 and the art. 163 cash-accounting family.
- Bind Modelo 303 casillas 62/63/74/75 in both committed revisions through `ledger_iva_aggregation`.
- Add real-behavior tests for aggregation projection and registry binding resolution.

## Outcome

Commit `246ba49ae4` implements the S281 slice. Casillas 62/63/74/75 are no longer dangling manual rows in the targeted revisions: each has matching bindings, construct membership, and legal-ref closure. Ordinary domestic rows do not populate the cash-accounting informational boxes; rows carrying the new cash-accounting axis do.

Focused verification passed:

- `uv run --no-sync pytest -q src/aeat/application/aggregation/tests/test_iva_cash_accounting.py src/aeat/domain/calculations/registry/tests/test_modelo_303_cash_accounting.py` - 4 passed.
- `uv run --no-sync vaultspec-core vault check features --feature cross-domain-continuity` - clean.
- `uv run --no-sync vaultspec-core vault check schema --feature cross-domain-continuity` - clean.
- `uv run --no-sync vaultspec-core vault check references --feature cross-domain-continuity` - clean.

## Notes

Wholely unpaid fallback-only cash-accounting operations remain intentionally rejected rather than silently projected. The landed slice supports explicit payment evidence and statutory fallback remainders from partial evidence. A full-vault check still reports unrelated legacy/peer vault hygiene warnings; those were left untouched.
