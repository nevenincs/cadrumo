---
tags:
  - '#exec'
  - '#binding-source-kind-taxonomy-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S01'
related:
  - "[[2026-06-26-binding-source-kind-taxonomy-unification-plan]]"
---




# Add BORRADOR and IVA_WALLET_DECISION members to BindingSourceKind

## Scope

- `src/aeat/core/aggregation.py`

## Description


P01.S01 and P01.S02 landed together as one atomic commit `b869dcda4`
(`relocation:BindingSourceKind`), because adding the members without the gate
extension would red the existing enum-registry orphan gate.

- Add `BORRADOR = "borrador"` and `IVA_WALLET_DECISION = "iva_wallet_decision"`
  to `BindingSourceKind` in `src/aeat/core/aggregation.py`, documented as
  mesh-only sourcing decisions resolved by a pre-mesh gate with no registry
  binding by design. Each member takes the VALUE of the pre-existing mesh
  string, so the lift is behaviour-preserving.
- Extend the domain enum-registry parity gate
  (`src/aeat/domain/calculations/registry/tests/test_binding_source_kind_taxonomy.py`)
  with a `_MESH_ONLY_SOURCE_KINDS` carve-out exempting the two members from the
  orphan gate and asserting they stay disjoint from the registry-declared set.
- Add the application enum-mesh parity half as a new sibling test
  (`src/aeat/application/modelo/tests/test_binding_source_kind_mesh_parity.py`):
  every owned/deferred mesh source is a `BindingSourceKind` member, every member
  is routed/deferred/reserved, the owned and deferred sets are disjoint, and the
  two new members are proven routed-owned with an anti-tautology reserved check.

## Outcome

P01 complete. Both parity halves green (14 tests), the related boundary and
enrollment suite green (26 tests total in the combined run), and
`pytest --collect-only -q src/aeat` collects cleanly. No casilla value shifts:
the StrEnum lift changes static types only.

## Notes

S02 layering decision: the enum-mesh half could NOT live in the existing domain
test, because the mesh sets (`_BUCKET_AGGREGATION_OWNED_SOURCES`,
`DEFERRED_SOURCE_KINDS`) are application-layer symbols and a domain test
importing them violates the hexagonal direction (domain to application is
forbidden). It was implemented as a new application-layer sibling test marked
`hex_application`, the same layer and home pattern as the existing
source-boundary enrollment gate, keeping the assertion real (it imports and
checks the live mesh sets) rather than tautological.

The two new members are mesh-resolved with no registry binding, so they were
given an explicit mesh-only disposition (`_MESH_ONLY_SOURCE_KINDS`), NOT placed
in the reserved-undeclared bucket (which is for not-yet-wired tokens awaiting a
future registry binding).

P02.S03 surfaced a genuine design conflict with the ADR (reported to the
coordinator, work paused there): the two `source_kind` carriers on
`CalculationSourceDiagnostic` / `CalculationSourceProvenance` are a documented
diagnostic/provenance channel deliberately overloaded with NON-source-kind
tokens (`transaction_evidence`, `local_filing`, `mixed_observation_sources`,
`aeat_sede_iva_compensation_history`). Re-typing them to `BindingSourceKind` as
the ADR Implementation section 3 specifies would break those legitimate tokens
or force a category-error widening of the enum. The `owned_sources` and
`DEFERRED_SOURCE_KINDS` halves of S03 are clean and unconflicted.
