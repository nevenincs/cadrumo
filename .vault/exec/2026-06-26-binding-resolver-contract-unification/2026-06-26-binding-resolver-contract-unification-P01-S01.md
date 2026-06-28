---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S01'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---




# Retire the advertised-canonical CasillaAggregation/CasillaProvenance framing from the package docstring, keeping the live ledger-aggregation classes but removing the bypassed canonical claim

## Scope

- `src/aeat/application/aggregation/__init__.py`

## Description


Commit `ae2ed0a5f`. Refined the aggregation package docstring so
`CasillaAggregation` / `CasillaProvenance` read as the per-modelo
ledger-aggregation value records produced by the `aggregate_*` family, NOT a
canonical resolved-source envelope; named `CalculationSourceResolution` as the one
canonical resolved-source envelope every mesh resolver returns.

## Outcome

P01.S01 complete. The live `CasillaAggregation` / `CasillaProvenance` classes and
re-exports are kept (coordinator adj#2); only the advertised-canonical framing is
retired. Docstring-only; no behaviour change.

## Notes


Landed via explicit-pathspec commit while a peer had files staged in the shared
index, scoped to `__init__.py` only so the peer's staged work was preserved.
