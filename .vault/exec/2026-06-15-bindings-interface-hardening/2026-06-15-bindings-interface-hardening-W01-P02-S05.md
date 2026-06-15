---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S05'
related:
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---




# derive every per-family source-kind frozenset from the canonical enum, fix the incomplete LEDGER_BINDING_SOURCE_KINDS, and reconcile every consumer into one accept-or-reject state per the retired-enum rule

## Scope

- `src/aeat/domain/calculations/registry/_ledger_bindings.py`
- `src/aeat/domain/calculations/registry/_invoice_bindings.py`
- `src/aeat/core/aggregation.py`

## Description

- Define `INVOICE_BINDING_SOURCE_KINDS` and `LEDGER_BINDING_SOURCE_KINDS` in `core/aggregation.py` as frozensets derived from `BindingSourceKind` members (not hand-listed strings).
- Fix the historically incomplete `LEDGER_BINDING_SOURCE_KINDS`: it now covers all four ledger kinds (oss, iva, renta_expense, renta_income) where it previously listed only iva and renta_expense.
- Replace the hand-listed frozenset literals in `_invoice_bindings.py` and `_ledger_bindings.py` with re-exports of the core-derived sets, keeping the existing public names (`__all__`) and registry-package re-exports intact so every consumer routes through one source of truth.
- Confirm the counterpart family set (`COUNTERPART_BINDING_SOURCE_KINDS = COUNTERPART_SOURCE_KINDS`) is already enum-derived from `AggregationSourceKind` whose values align with `BindingSourceKind`; no change needed.
- Leave the application-layer `_BUCKET_AGGREGATION_OWNED_SOURCES` and `DEFERRED_SOURCE_KINDS` mesh-ownership sets untouched (settled mesh side); only the binding-definition-family sets were re-derived.

## Outcome

The three per-family source-kind collections are now derived subsets of the single `BindingSourceKind` taxonomy. The ledger preflight in `state_projection.py` (which imports `LEDGER_BINDING_SOURCE_KINDS`) now correctly identifies modelos bound to OSS and renta-income ledger aggregation that the two-member set previously missed; the state-projection, ledger-preflight, simplificado-bypass, and bucket-aggregation-flow suites pass with the broadened set.

## Notes

The mesh-ownership sets intentionally include resolver-owned source kinds (`borrador`, `iva_wallet_decision`) that are not binding `source` tokens, so they are not — and must not be — derived from `BindingSourceKind`. The reconciliation is therefore scoped to the binding-definition families (invoice, ledger, counterpart) per the brief's "do not change which kinds are owned vs deferred" constraint.
