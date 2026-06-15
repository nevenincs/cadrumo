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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace bindings-interface-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S05 and 2026-06-15-bindings-interface-hardening-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The derive every per-family source-kind frozenset from the canonical enum, fix the incomplete LEDGER_BINDING_SOURCE_KINDS, and reconcile every consumer into one accept-or-reject state per the retired-enum rule and ## Scope

- `src/aeat/domain/calculations/registry/_ledger_bindings.py`
- `src/aeat/domain/calculations/registry/_invoice_bindings.py`
- `src/aeat/core/aggregation.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
