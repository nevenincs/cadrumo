---
name: binding-validation-single-contract
trigger: always_on
---

# Binding validation: one contract, enforced at registry build

Every registry binding `source` family MUST expose a single
`validate(binding) -> list[str]` validator — accumulating, never raising —
registered in the one binding-validator dispatch table keyed by
`BindingSourceKind`, and run by the registry-build section validator for ALL
families.

A binding's op and fact invariants MUST be enforced at **registry-build** time,
never resolve-time-only. Resolve-time helpers may remain as defence-in-depth
backstops. Preserve the underlying pydantic field error in the diagnostic —
never flatten it to a generic "malformed selector".

Validation was scattered across three incompatible conventions — validators that
raised, a list accumulator, and no public validator at all for several families —
with invariants run at build for some sources and only at resolve time for
others. A malformed binding for those families shipped clean through snapshot
build and failed only when a taxpayer's calculation ran.

## How

- **Good:** a new family is added to the dispatch table with a
  `validate(binding) -> list[str]` entry; the build-time section validator runs it
  for every binding of that source and accumulates failures in one pass, routing
  the selector through `selector_as_dict` and surfacing the field message
  verbatim.
- **Bad:** a per-family validator that raises, or a private validated selector
  invoked only inside the resolver — that re-creates the build-versus-resolve
  split this rule closes.
- **Bad:** flattening the selector error, losing the field that drifted.

Sibling binding contracts: `binding-aggregation-is-typed` (typed op enum),
`binding-source-kind-single-taxonomy` (the closed source set),
`binding-values-carry-provenance` (grounding on the value).

Source: ADR `2026-06-14-bindings-interface-hardening-adr` (decision A); gate
`test_binding_build_validation.py`.
