---
name: binding-aggregation-is-typed
trigger: always_on
---

# Binding aggregation is a typed model with a closed op enum

## Rule

A registry binding's aggregation MUST be the typed `BindingAggregation` model
carrying a closed `BindingAggregationOp` enum (declared in `aeat.core`), never a
free-form `Mapping`. No call site may re-parse `aggregation.get("op")` from a raw
mapping or pick its own local default; the single `binding_aggregation_op(binding)`
accessor returns the typed op and applies the one declared per-family default in
one place.

## Why

The bindings-interface discovery found `aggregation` was a free-form
`Mapping[str, ...]` and `op` was re-derived as
`str((binding.aggregation or {}).get("op", <default>))` at ~10 sites with
divergent silent defaults (`"sum"` for the scalar-folding families, `"rows"` for
the detail-record families). The default op was therefore silently
source-dependent and unauditable, and an unknown op was caught only at resolve
time. Typing the model rejects an unknown op at registry-build, and one accessor
makes the per-family default declared data rather than scattered string literals.
Recorded in ADR `2026-06-14-bindings-interface-hardening-adr` (decision B);
exercised by `test_binding_aggregation.py`.

## How

- **Good:** read a binding's op via `binding_aggregation_op(binding)`; it returns
  a `BindingAggregationOp` member and applies the declared default for the
  binding's source when `aggregation is None`.
- **Good:** a new op value is added to the `BindingAggregationOp` enum (the
  complete registry set), so the typed field validates it at build.
- **Bad:** `str((binding.aggregation or {}).get("op", "sum"))` inline in a
  resolver — re-introduces the untyped re-parse and a local default.
- **Bad:** widening `aggregation` back to a bare mapping, or stuffing arbitrary
  keys beyond the typed model.

## Source

ADR `2026-06-14-bindings-interface-hardening-adr` (decision B), research
`2026-06-14-bindings-interface-hardening-research` (cluster B). The relation and
formula-expression `op` axes are separate concepts and are out of scope. Companion
to `aeat-architecture-boundaries` (closed value sets are enums in `core`).
