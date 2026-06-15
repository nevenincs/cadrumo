---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S07'
related:
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---




# add a taxonomy parity gate asserting the canonical source-kind enum equals the registry binding source set

## Scope

- `src/aeat/domain/calculations/registry/tests/test_binding_source_taxonomy.py`

## Description

- Add the parity gate `test_binding_source_kind_taxonomy.py` under the registry tests folder, modelled on the `Modelo`/`registry_modelo_codes()` parity gate.
- Assert every binding `source` declared across all compiled registry revisions is a `BindingSourceKind` member (loader-built subset check over the full tree).
- Assert no enum member is an undeclared orphan, with a documented `_RESERVED_UNDECLARED_SOURCE_KINDS` carve-out (payable_invoice, purchase_invoice_evidence, ledger_transaction) mirroring the `NON_REGISTRY_MODELOS` pattern — these are code-load-bearing but registry-undeclared, fenced as out-of-scope-but-tracked in the ADR — and a counter-assertion that a reserved member which gains a registry declaration must leave the carve-out.
- Assert each per-family frozenset equals its derived enum subset: invoice (3 members), ledger (all 4 — guarding the historical 2-of-4 regression), and counterpart (4, value-mapped from `AggregationSourceKind`); assert invoice and ledger are disjoint.
- Add the anti-tautology proof: a bogus source string is rejected by the typed field; and a round-trip proving each member validates from and serialises to its exact stored token (behaviour-preserving lift).

## Outcome

Eight assertions, all passing. The gate locks `BindingSourceKind` to the registry as the authority for which tokens exist and locks every per-family frozenset to its derived subset, so a future hand-edit that re-fragments the taxonomy or re-shrinks the ledger set fails loudly. The orphan carve-out surfaced and documents the three ADR-fenced code-only source kinds honestly rather than silently passing.

## Notes

The file is named `test_binding_source_kind_taxonomy.py` (the scaffold scope line read `test_binding_source_taxonomy.py`); the `_kind_` infix matches the `BindingSourceKind` type it gates and the project's existing `test_*_kind*` naming. The orphan test was tightened after the first run: an initial zero-orphan assertion correctly failed on the three registry-undeclared-but-code-live members, which is the expected ADR-fenced state, so the carve-out constant was added with a stated reason rather than weakening the gate.
