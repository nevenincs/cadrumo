---
name: registry-resolver-family-extraction
trigger: always_on
---

# Registry binding and resolver families live in per-family modules

## Rule

A registry binding or resolver family — counterpart, ledger, invoice,
detail-record, withholding, previous-filing, and any new one — MUST live in its
own per-family module under `domain/calculations/registry/`, consumed only
through the package's top-level `__all__` facade. New families follow the
established per-family shape: selector model, typed validator registered in the
dispatch table, and `resolve_*` functions. The `_bindings.py` aggregator holds
the cross-family dispatch table and re-exports; it does not accrete family
implementations.

## Why

`_bindings.py` had grown into a multi-thousand-line module mixing roughly fifteen
resolver families, with a private selector coupling into the formula runtime.
Per-family extraction behind the package facade keeps the aggregator from
re-accreting and keeps cross-package consumers on the facade rather than dotting
into a family's internals.

## How

- **Good:** a new source family lands as `_<family>_bindings.py` carrying its
  selector model, its `validate(binding) -> list[str]` entry in the dispatch
  table, and its `resolve_*` functions, re-exported through the registry
  package's `__all__`. Consumers import from the package top level.
- **Bad:** adding a new family's selector, validator, or resolver inline into
  `_bindings.py`, regrowing the monolith.
- **Bad:** a consumer importing from a family's private submodule instead of the
  package facade.

## Source

Audit `2026-06-02-registry-bindings-boundary-audit` and ADR
`2026-06-14-bindings-interface-hardening-adr` (decision F). Companions:
`service-imports-via-top-level-reexports`, `aeat-architecture-boundaries`.
