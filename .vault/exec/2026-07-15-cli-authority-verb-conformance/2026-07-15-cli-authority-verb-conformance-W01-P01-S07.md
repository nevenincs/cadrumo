---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S07'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Require a non-optional TransactionCatalogueRepositoryProtocol in the public IRNR source resolver

## Scope

- `src/cadrumo/application/aggregation/_modelo_bindings.py`

## Description

- Search the semantic code index for the IRNR resolver, required transaction repository, and memoized source mesh.
- Enumerate the public export, constructor sites, resolver calls, focused tests, and repository Protocol members with exact source searches.
- Require `TransactionCatalogueRepositoryProtocol` in `LedgerIrnrIncomeAggregationSourceResolver.__init__` without changing any neighboring resolver default.
- Run focused lint and real-behavior tests for M210 aggregation, memoized repository behavior, and source-resolver enrollment.

## Outcome

- The semantic query directly found the already-required repository loader and its Protocol boundary; exact searches completed the public constructor graph.
- The public resolver has one production construction in `_resolve_bucket_source_mesh`, which injects the shared `_MemoizedTransactionCatalogueRepository`; no second constructor, compatibility default, overload, fallback, or alternate IRNR composition door remains.
- The Protocol requires `bucket_id`, `exists`, `load`, `load_for_date_range`, `partition_by_date_range`, and `save`; both the concrete encrypted repository and the memoized wrapper provide those members.
- Ruff passed for the changed module.
- The focused M210, memoized repository, and source-resolver enrollment suites passed 11 tests in 47.49 seconds.

## Notes

- An initial one-line mechanical patch matched an identical neighboring resolver signature. Immediate diff inspection caught it before any gate or record closure; the neighboring signature was restored and the final source diff changes only the IRNR constructor.
- Existing peer work in `_calculation_actions.py` remained untouched and outside the commit; its shared memoized construction path was inspected read-only.
- S08 was not started.
