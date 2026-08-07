---
name: binding-validation-single-contract
trigger: always_on
---

# Binding validation: one contract, enforced at registry build

## Rule

Every registry binding `source` family MUST expose a single
`validate(binding) -> list[str]` validator — accumulating, never raising —
registered in the one binding-validator dispatch table keyed by
`BindingSourceKind`, and run by the registry-build section validator for ALL
families.

A binding's op and fact invariants MUST be enforced at **registry-build** time,
never resolve-time-only. Resolve-time helpers may remain as defence-in-depth
backstops. The underlying pydantic field error MUST be preserved in the
diagnostic, never flattened to a generic "malformed selector".

## Why

Validation was scattered across three incompatible conventions — public
validators that raised, a list accumulator, and no public validator at all for
several families — with op and fact invariants run at build for some sources and
only at resolve time for others. A malformed binding for those families shipped
clean through snapshot build and failed only when a taxpayer's calculation ran.
One contract run at build for every family makes a malformed binding a loud
build failure uniformly, closing the stricter-than-runtime and
looser-than-runtime gradient.

## How

- **Good:** a new source family is added to the validator dispatch table with a
  `validate(binding) -> list[str]` entry; the build-time section validator runs
  it for every binding of that source and accumulates failures in one pass.
- **Good:** the validator routes the selector through `selector_as_dict` for
  normalisation and surfaces the pydantic field message verbatim.
- **Bad:** adding a per-family validator that raises, or a private validated
  selector invoked only inside the resolver — that re-creates the
  build-versus-resolve split this rule closes.
- **Bad:** flattening the selector validation error to a generic string, losing
  the field that drifted.

## Source

ADR `2026-06-14-bindings-interface-hardening-adr` (decision A). Exercised by
`test_binding_build_validation.py`. Companions:
`aeat-registry-authority-flow`, `no-silent-under-declaration`.
