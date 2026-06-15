---
name: binding-validation-single-contract
---

# Binding validation: one contract, enforced at registry-build

## Rule

Every registry binding `source` family MUST expose a single
`validate(binding) -> list[str]` validator (accumulating, never raising),
registered in the one binding validator dispatch table keyed by
`BindingSourceKind`, and run by the registry-build section validator for ALL
families. A binding's op/fact invariants MUST be enforced at registry-build
time, never resolve-time-only; resolve-time helpers may remain only as
defence-in-depth backstops, and the underlying pydantic field error MUST be
preserved in the diagnostic (never flattened to a generic "malformed selector").

## Why

The bindings-interface discovery found validation scattered across three
incompatible conventions — public `validate_* -> None` that raised (invoice,
ledger), a `-> list[str]` accumulator (withholding), and no public validator at
all (counterpart, the four detail-record families) — with op/fact invariants run
at registry-build for counterpart/withholding but only at resolve time for the
detail-record families and `previous_filing`. A malformed binding for those
families shipped clean through snapshot build and failed only when a taxpayer's
calculation ran. One contract, run at build for every family, makes a malformed
binding a loud registry-build failure for all sources uniformly, closing the
stricter-than-runtime / looser-than-runtime gradient. Recorded in ADR
`2026-06-14-bindings-interface-hardening-adr` (decision A); the build gate is
exercised by `test_binding_build_validation.py`.

## How

- **Good:** a new source family is added to the `_BINDING_VALIDATOR_REGISTRY`
  dispatch table with a `validate(binding) -> list[str]` entry; the registry-build
  section validator runs it for every binding of that source and accumulates
  failures in one pass.
- **Good:** the validator routes the selector through `selector_as_dict` for
  normalisation and surfaces the pydantic field message verbatim.
- **Bad:** adding a per-family `validate_*_binding_definition` that raises, or a
  private `_validated_*_selector` invoked only inside the resolver — that
  re-creates the build-vs-resolve split this rule closes.
- **Bad:** flattening the selector validation error to a generic string, losing
  the field that drifted.

## Source

ADR `2026-06-14-bindings-interface-hardening-adr` (decision A), research
`2026-06-14-bindings-interface-hardening-research` (cluster A). Companion to
`aeat-registry-authority-flow` (the registry is the authority) and
`no-silent-under-declaration`.
