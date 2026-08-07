# Relation-targeted slot bindings declare relation_prefill

A binding that exists only as a relation's `target_binding` materialisation slot
MUST declare `source = "relation_prefill"`, never `source = "previous_filing"`.
A `previous_filing` binding MUST satisfy the direct-selector predicate, and
registry validation refuses a binding that is both relation-targeted AND
previous-filing-resolvable — the M303 IVA-wallet compensación slot being the sole
documented carve-out.

The cross-modelo fold-in overlap had a single root cause: relation
`target_binding` slots were mislabelled `previous_filing` for a value only
relation resolution could produce, so one fold-in looked like two mechanisms and
the enrolled `previous_filing` resolver skipped the non-direct slot by design,
leaving it dormant. Re-stamping the slot and gating the collision at
registry-compile time makes the dual-modelling structurally impossible.

## How

- **Good:** a relation-targeted slot declares `source = "relation_prefill"`; the
  collision gate confirms no binding is both relation-targeted and direct
  previous-filing-resolvable.
- **Good:** a same-modelo direct carry keeps `source = "previous_filing"` and
  passes the direct-selector predicate. The M303 compensación slot is the named
  carve-out, owned pre-mesh by the IVA-wallet gate.
- **Bad:** a relation `target_binding` slot declaring `previous_filing` with a
  non-direct selector — the registry gate now refuses it instead of letting the
  enrolled resolver silently skip it.

Source: ADR `2026-06-10-calculation-aggregation-taxonomy-adr`; gate
`domain/calculations/registry/_validate_relation_sources.py`.
