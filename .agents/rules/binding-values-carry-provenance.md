---
name: binding-values-carry-provenance
trigger: always_on
---

# Binding values carry provenance at casilla parity

## Rule

Every persisted and operator-facing binding value MUST carry its `legal_refs` and
`source_refs` and a typed `BindingSourceKind` source, at parity with casilla
provenance (`ModeloCasillaProvenance`). The filing builder populates them from the
binding definition; a hardcoded free-text source string (e.g. `"registry binding
input"`) is forbidden. The CLI bindings list/preview payloads MUST expose the same
grounding and be typed models, never an untyped `dict` bag.

## Why

The discovery found a provenance asymmetry at exactly the operator boundary:
casilla values carried full `legal_refs`/`source_refs` to draft and export, but
binding values were flattened to a hardcoded `source="registry binding input"`
with no grounding on the `ModeloBindingValue` carrier or the CLI payloads — even
though the registry binding definitions hold that grounding and the export layer
still emits it. An operator inspecting or filing a bound value could not see its
legal basis: the bindings half silently breached `aeat-calculation-grounding`
that the casilla half upholds. Recorded in ADR
`2026-06-14-bindings-interface-hardening-adr` (decision D); the encrypted-boundary
roundtrip + anti-tautology proof is `test_binding_value_provenance_roundtrip.py`.

## How

- **Good:** `ModeloBindingValue` carries `legal_refs`/`source_refs` +
  `source: BindingSourceKind`; the filing builder reads `binding.legal_refs` /
  `binding.source_refs` / `binding.source` from the definition it already holds.
- **Good:** `bindings list` returns a typed `BindingRowPayload` sequence carrying
  the grounding, not `list[dict[str, object]]`.
- **Bad:** constructing a `ModeloBindingValue` with a literal free-text `source`
  string, or dropping the binding definition's grounding at the builder.
- **Bad:** a bindings CLI payload that omits `legal_refs`/`source_refs` while the
  casilla payload carries them.

## Source

ADR `2026-06-14-bindings-interface-hardening-adr` (decision D), research
`2026-06-14-bindings-interface-hardening-research` (cluster D). Companion to
`aeat-calculation-grounding` (provenance through every boundary),
`aeat-roundtrip-discipline` (the persistence-boundary tests), and
`cli-notices-are-the-only-diagnostic-channel`.
