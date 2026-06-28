---
name: relation-slot-bindings-declare-relation-source
---

# Relation-targeted slot bindings declare relation_prefill

## Rule

A binding that exists only as a relation's `target_binding` materialisation slot
MUST declare `source = "relation_prefill"`, never `source = "previous_filing"`; a
`previous_filing` binding MUST satisfy the direct-selector predicate
(`_is_direct_previous_filing_binding`,
`src/aeat/domain/calculations/registry/_bindings_previous_filing.py`), and
registry validation refuses a binding that is both relation-targeted AND
previous-filing-resolvable — the M303 iva-wallet compensación slot being the sole
documented carve-out.

## Why

ADR `2026-06-10-calculation-aggregation-taxonomy-adr` (Implementation §3,
slot-binding hygiene) found the cross-modelo fold-in overlap had a single root
cause: relation `target_binding` slots were mislabelled `source = "previous_filing"`
for a value only relation resolution could produce, so one fold-in looked like two
mechanisms and the enrolled `previous_filing` resolver skipped the non-direct slot
by design, leaving it dormant. Re-stamping the slot `relation_prefill` and gating
the collision at registry-compile time makes the dual-modelling structurally
impossible (defence in depth per `composition-service-no-parallel-write-path`).

## How

- Good: a relation-targeted M100/M180/M190/M193/M200/M202 slot binding declares
  `source = "relation_prefill"`; the collision gate in
  `domain/calculations/registry/_validate_relation_sources.py` confirms no binding
  is both relation-targeted and direct-previous_filing-resolvable.
- Good: a same-modelo direct carry keeps `source = "previous_filing"` and passes
  `_is_direct_previous_filing_binding`; the M303
  `modelo-303-compensacion-pendiente-anteriores` slot is the named carve-out
  (`_IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS`,
  `_validate_relation_sources.py:42`) — owned pre-mesh by the iva-wallet gate.
- Bad: a relation `target_binding` slot declaring `source = "previous_filing"`
  with a non-direct selector — the registry gate now refuses it instead of letting
  the enrolled resolver silently skip it.
- Bad: a binding that is both a relation `target_binding` and a direct
  previous_filing carry (outside the M303 carve-out) — the collision gate rejects
  it at compile time.
