---
name: binding-aggregation-is-typed
trigger: always_on
---

# Binding aggregation is a typed model with a closed op enum

A registry binding's aggregation MUST be the typed `BindingAggregation` model
carrying a closed `BindingAggregationOp` enum declared in `cadrumo.core`, never a
free-form `Mapping`. No call site may re-parse `aggregation.get("op")` from a raw
mapping or pick its own local default: the single `binding_aggregation_op(binding)`
accessor returns the typed op and applies the one declared per-family default in
one place. A new op value is added to the enum, so the typed field validates it
at registry build.

`aggregation` was a free-form mapping and `op` was re-derived at roughly ten
sites with **divergent silent defaults** — one for the scalar-folding families,
another for the detail-record families — so the effective default was
source-dependent and unauditable, and an unknown op was caught only at resolve
time.

## How

- **Bad:** `str((binding.aggregation or {}).get("op", "sum"))` inline in a
  resolver — the untyped re-parse plus a local default.
- **Bad:** widening `aggregation` back to a bare mapping, or stuffing arbitrary
  keys beyond the typed model.

The relation and formula-expression `op` axes are separate concepts and are out
of scope.

Full binding contract: `binding-validation-single-contract`. Source: ADR
`2026-06-14-bindings-interface-hardening-adr` (decision B); gate
`test_binding_aggregation.py`.
