---
name: registry-resolver-family-extraction
trigger: always_on
---

# Registry binding and resolver families live in per-family modules

A registry binding or resolver family — counterpart, ledger, invoice,
detail-record, withholding, previous-filing, and any new one — MUST live in its
own per-family module under `domain/calculations/registry/`, consumed only
through the package's top-level `__all__` facade. New families follow the
established shape: selector model, typed validator registered in the dispatch
table, and `resolve_*` functions. The `_bindings.py` aggregator holds the
cross-family dispatch table and re-exports; it does not accrete family
implementations.

`_bindings.py` had grown into a multi-thousand-line module mixing roughly fifteen
families, with a private selector coupling into the formula runtime.

## How

- **Bad:** adding a new family's selector, validator, or resolver inline into
  `_bindings.py`, regrowing the monolith; or a consumer importing from a family's
  private submodule instead of the package facade.

Source: audit `2026-06-02-registry-bindings-boundary-audit`, ADR
`2026-06-14-bindings-interface-hardening-adr` (decision F). Companion:
`service-imports-via-top-level-reexports`.
