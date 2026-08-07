# Binding values carry provenance at casilla parity

## Rule

Every persisted and operator-facing binding value MUST carry its `legal_refs`
and `source_refs` and a typed `BindingSourceKind` source, at parity with casilla
provenance. The filing builder populates them from the binding definition it
already holds; a hardcoded free-text source string is forbidden. The CLI
bindings list and preview payloads MUST expose the same grounding and MUST be
typed models, never an untyped dict bag.

## Why

There was a provenance asymmetry at exactly the operator boundary: casilla
values carried full grounding through to draft and export, while binding values
were flattened to a hardcoded source string with no grounding on the value
carrier or the CLI payloads — even though the registry binding definitions hold
that grounding and the export layer still emits it. An operator inspecting or
filing a bound value could not see its legal basis, so the bindings half
silently breached the grounding rule that the casilla half upholds.

## How

- **Good:** `ModeloBindingValue` carries `legal_refs`, `source_refs` and
  `source: BindingSourceKind`; the filing builder reads them from the binding
  definition.
- **Good:** `bindings list` and preview return typed payload sequences carrying
  the grounding, not `list[dict[str, object]]`.
- **Bad:** constructing a `ModeloBindingValue` with a literal free-text source,
  or dropping the definition's grounding at the builder.
- **Bad:** a bindings CLI payload that omits grounding while the casilla payload
  carries it.

## Source

ADR `2026-06-14-bindings-interface-hardening-adr` (decision D). Encrypted-boundary
roundtrip and anti-tautology proof in
`test_binding_value_provenance_roundtrip.py`. Companions:
`aeat-calculation-grounding`, `aeat-roundtrip-discipline`,
`cli-notices-are-the-only-diagnostic-channel`.
