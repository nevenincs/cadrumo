---
name: registry-resolver-family-extraction
---

# Registry binding/resolver families extract into per-family modules

## Rule

A registry binding or resolver family (counterpart, ledger, invoice,
detail-record, withholding, previous-filing, …) MUST live in its own per-family
module under `domain/calculations/registry/`, consumed only through the package
top-level `__all__` facade. New families follow the established per-family module
shape (selector model + typed validator registered in the dispatch table +
`resolve_*` functions) rather than growing the `_bindings.py` aggregator. The
aggregator re-exports; it does not accrete family implementations.

## Why

The `2026-06-02-registry-bindings-boundary-audit` found `_bindings.py` had grown
to a ~3,000-line module mixing ~15 resolver families with a private selector
coupling into `_formula_runtime.py`; it proposed a staged per-family extraction
behind re-exports as the codify candidate `registry-resolver-family-extraction`,
which was never promoted. The bindings-interface-hardening campaign confirmed the
shape: families already split into `_counterpart_bindings.py`, `_ledger_bindings.py`,
`_invoice_bindings.py`, `_detail_record_bindings.py`, `_withholding_bindings.py`,
and `_bindings_previous_filing.py`, with one validator dispatch table in
`_bindings.py`. Codifying the discipline keeps the aggregator from re-accreting and
keeps cross-package consumers on the package facade rather than dotting into a
family's internals. Promoted per the `vaultspec-codify` discipline after the shape
held across the campaign.

## How

- **Good:** a new source family lands as `_<family>_bindings.py` (selector model,
  `validate(binding) -> list[str]` in the dispatch table, `resolve_*`), re-exported
  through the registry package `__all__`; consumers import from the package top
  level.
- **Good:** `_bindings.py` holds the cross-family dispatch table and re-exports,
  not per-family resolver bodies.
- **Bad:** adding a new family's selector/validator/resolver inline into
  `_bindings.py`, regrowing the monolith.
- **Bad:** a consumer importing `from ...registry._counterpart_bindings import ...`
  (dotting into a family's private submodule) instead of the package facade.

## Source

Audit `2026-06-02-registry-bindings-boundary-audit` (codify candidate, never
promoted) and ADR `2026-06-14-bindings-interface-hardening-adr` (decision F).
Companion to `service-imports-via-top-level-reexports` and
`aeat-architecture-boundaries` (relocation atomicity).
