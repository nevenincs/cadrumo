---
tags:
  - '#adr'
  - '#binding-resolver-contract-unification'
date: '2026-06-26'
modified: '2026-06-26'
related:
  - "[[2026-06-26-bindings-architecture-unification-audit]]"
  - "[[2026-06-26-bindings-architecture-unification-research]]"
  - "[[2026-06-26-binding-source-kind-taxonomy-unification-adr]]"
  - "[[2026-05-20-calculation-source-connectivity-adr]]"
  - "[[2026-06-10-calculation-aggregation-taxonomy-adr]]"
---



# `binding-resolver-contract-unification` adr: `resolver-contract unification: one source-resolver port and one result envelope across the calculate mesh` | (**status:** `proposed`)

> PROPOSED — design-ahead for coordinator review, authored while phase-2.1 code is
> gated on the #6/#28 peer landing. NOT self-accepted and NOT a code-execution
> request; it does not jump the code sequence (phase 2.2 executes after phase 2.1).
> This is phase 2.2 of the bindings-architecture-unification sweep; the canonical
> direction is the phase + foundational ADRs (no apex).

## Problem Statement

Phase 2.2 of the bindings-architecture-unification sweep, grounded in the breadth
audit (`2026-06-26-bindings-architecture-unification-audit`, findings F2 and F5) and
the decision-corpus reconciliation. Where phase 2.1 makes the source-kind closed set
one typed authority, phase 2.2 makes the way a source value is RESOLVED one contract.

The defect (audit F2/F5, verified at HEAD): a non-registry source value is produced
through one of THREE structurally distinct, unreconciled contracts. (A) the source
mesh — the `ModeloSourceResolver` Protocol returning the rich `CalculationSourceResolution`
(the live calculate path, ~12 resolvers). (B) a pre-mesh `BindingSourceResolution`
Protocol returning `ProfileSourcedBindingResult` / `Modelo100BorradorBindingResult`
(profile and borrador run OUTSIDE the mesh, with a separate precedence ladder; a
profile value is shape-converted B→A→B on every calculation — pure friction). (C) the
per-modelo aggregation service (`aggregate_per_modelo`) returning `PerModeloAggregationResult`,
keyed off the now-superseded `AggregationSourceKind` (the CLI `aggregate` verb path;
counterpart 347/349 and foreign-assets 720 are reachable ONLY here and never enter the
live calculate mesh; retenciones is reachable through BOTH A and C with two result
types). Beyond the three live shapes, four-to-six vestigial or near-dead result
envelopes model the same "a resolved source value" role (`CalculationBindingResolution`,
the advertised-but-bypassed `CasillaAggregation`, the M349-only
`PerModeloRegistryBindingResolution`, the consumer-less `ModeloLedgerBindingAggregation`).
And (F5) a source's ENROLLMENT state — enrolled / pre-mesh-handled / deferred /
service-only — is tracked in FOUR disconnected structures with no parity gate, so the
`no-dormant-source-resolvers` rule is declared but unenforceable across the union, and
counterpart/720 are silently orphaned from the live path.

## Considerations

This ADR is fenced to the resolver CONTRACT and ENVELOPE altitude; it does not reopen
the mesh PORT decision (`calculation-source-connectivity`, foundational) nor the
mechanism-ownership table (`calculation-aggregation-taxonomy`, foundational) — it
builds on both. It depends on phase 2.1 (the one `BindingSourceKind` authority): the
disposition registry and the parity gate below are typed on that enum, so phase 2.2
EXECUTION sequences after phase 2.1 lands. The fold-in/carry value-layer dedup is
phase 2.3 and the vocabulary/CLI pass is phase 2.4 — both out of scope here.

The load-bearing design tension is profile/borrador and the per-modelo service: are
they folded INTO the one mesh, or kept as formally-documented, test-gated exceptions?
The audit shows the B→A→B profile wrap is pure friction (fold it in), and the C
service orphans counterpart/720 from the live path (a correctness-adjacent gap, not
just friction). The decision below picks folding-in as the default and a documented
gated exception only where a genuine reason exists, never a silent parallel pipeline.

Project rules binding this: `calculation-source-canonical-mechanism` (one mechanism
per type — this ADR is its resolver-contract companion), `no-dormant-source-resolvers`
(the parity gate must make every source enrolled/deferred/reserved enforceable),
`one-aggregation-path-pull-equals-calculate` (the pull and calculate paths share one
resolver set — preserved), `aeat-architecture-boundaries` (one typed contract; no
parallel shapes), `composition-service-no-parallel-write-path` (a new surface
delegates, never re-implements), and `no-legacy-compatibility` (delete the vestigial
envelopes, do not alias).

## Constraints

- **Depends on phase 2.1 (the one source-kind authority).** The disposition registry
  and the parity gate are typed on `BindingSourceKind`; phase 2.2 execution sequences
  after phase 2.1 lands. This ADR is design-ahead only — it lands no code.
- **Correctness risk in the C-service fold, not just friction.** Counterpart (347/349)
  and foreign-assets (720) are reachable only through the shape-C service today; the
  fold-in must preserve their behaviour exactly (these feed real filings). The retenciones
  double-path (A and C) must collapse to one without changing the perceptor-count
  result the #6/#28 work just landed.
- **Profile/borrador are pre-mesh by an existing precedence decision.** Folding them
  into the mesh must preserve the caller-override precedence ladder and the
  `borrador-100` integration ADR's semantics (which phase 2.1 already reworks to a
  typed member); any retained pre-mesh step must be a documented, test-gated exception
  with a stated reason, not a silent parallel path.
- **Wide consumer blast radius, behaviour-preserving.** Re-homing ~12 resolvers and
  retiring 4-6 vestigial envelopes touches the live calculate path; every change is
  proven by the existing calculate/roundtrip suites plus the new parity gate, with no
  casilla value shift. Runs under the shared-branch report-before-land + abort-on-WIP
  discipline.

## Implementation

One port, one envelope, one disposition registry. Layering (the plan sequences the
steps; this is the shape):

1. **One result envelope.** `CalculationSourceResolution` is THE single resolved-source
   envelope. The vestigial / near-dead envelopes are retired per `no-legacy`:
   `CalculationBindingResolution`, the advertised-but-bypassed `CasillaAggregation`
   "canonical" framing, the M349-only `PerModeloRegistryBindingResolution`, and the
   consumer-less `ModeloLedgerBindingAggregation`. Their few real consumers migrate to
   the one envelope.

2. **Fold the pre-mesh shape into the mesh (end the B→A→B wrap).** Profile and borrador
   become first-class `ModeloSourceResolver`s returning `CalculationSourceResolution`
   directly, preserving the caller-override precedence ladder as explicit mesh-merge
   precedence rather than a separate pre-mesh stage. The `BindingSourceResolution`
   Protocol and the `ProfileSourcedBindingResult` / borrador wrap/unwrap are removed.
   If a genuine ordering reason requires a pre-mesh step for one source, it is a
   documented, test-gated exception naming the reason — never a silent second pipeline.

3. **Adjudicate the per-modelo aggregation service (shape C).** Counterpart (347/349)
   and foreign-assets (720) are brought onto the live calculate mesh as
   `ModeloSourceResolver`s (closing the orphan), and retenciones collapses to ONE path
   (the mesh resolver), retiring the duplicate service result type. Per
   `composition-service-no-parallel-write-path`, the CLI `aggregate` verb, if retained,
   DELEGATES to the one mesh resolver rather than re-implementing aggregation; the
   `PerModeloAggregationResult` shape is retired or reduced to a thin CLI projection of
   the one envelope.

   **Execution refinement (recorded 2026-06-26): counterpart 347/349 + foreign-assets
   720 fold SCOPED OUT of phase-2.2 to a grounded follow-up (task #36).** Execution
   found the counterpart/720 fold is NOT mechanical: `aggregate_counterpart_347/349` /
   `aggregate_foreign_assets_720` are reached only via the CLI `aggregate` path (shape
   C) and are NOT dormant mesh resolvers, AND M349's counterpart binding is ALREADY
   live on the calculate path via `InvoiceCatalogueSourceResolver` (a different
   mechanism, `resolve_invoice_binding_values` from `InvoiceObservation`). The
   standalone `CounterpartObservation`s that `aggregate_counterpart_*` consumes have NO
   context-reachable source on the calculate path (operator-supplied via the CLI
   payload only). So authoring a counterpart/720 mesh resolver requires DECIDING where
   those observations originate on the calculate path — either inventing a new
   counterpart-observation source (scope beyond mechanical delegation) or delegating
   over the invoice resolver's counterpart path (a `one-aggregation-path` parallel-path
   violation) — both of which this ADR's own rationale forbids. Because shape-C
   counterpart/720 are CLI-reachable (not dormant mesh resolvers) and M349 is already
   live, deferring them leaves NO dormant-mesh-resolver invariant breach. The follow-up
   (#36) grounds each of M347/M349/M720 per-modelo and acts per class: (a) already-live
   via an enrolled resolver (M349 = invoice) → no action; (b) genuinely UNROUTED on the
   calculate path = a silent-blank correctness finding → track + fix grounded; (c)
   served only by the redundant shape-C aggregate → retire shape-C, route to the
   canonical source. This is mini-research + a possible ADR amendment, not a phase-2.2
   step. The phase-2.2 plan Steps S10/S11/S12 (counterpart/720 author + enroll) and the
   S20/S21 correctness gates are deferred to #36; the **retenciones collapse (S13) + its
   correctness gate (S19) are KEPT** in phase-2.2 — retenciones is already canonical
   (the enrolled `RetencionesAggregationSourceResolver`, #6), so collapsing the
   redundant shape-C `aggregate_retenciones` to that one enrolled path IS mechanical and
   behaviour-preserving.

4. **One disposition registry + parity gate (closes F5).** A single declared mapping
   answers "where does source X resolve" for every `BindingSourceKind` member —
   enrolled-in-mesh / pre-mesh-documented-exception / deferred / reserved — replacing
   the four scattered structures (`merge_source_resolutions` tuple, `_pre_mesh_handled`,
   `DEFERRED_SOURCE_KINDS`, the service provider enum). A parity gate asserts the
   registry covers every enum member and equals the union of enrolled resolver
   `owned_sources`, making `no-dormant-source-resolvers` enforceable across the union.

A `{reference}` document will pin the concrete current-state anchors (every resolver
class, every envelope type, the four enrollment structures) the plan edits.

## Rationale

The project already decided one port and one mechanism-ownership table; the breach is
that two more sourcing pipelines (the pre-mesh wrap and the per-modelo service) grew
up beside the mesh, plus a litter of envelopes for one role. Collapsing to one port +
one envelope is the `aeat-architecture-boundaries` "one typed contract" applied to the
half that drifted, and it is what makes the resolver layer legible: a reader learns
one shape, not three. Folding C in (rather than documenting it as a permanent separate
surface) is required because it orphans counterpart/720 from the live path — a
coherence and coverage gap, not mere style. The disposition registry + parity gate is
the durable enforcement that converts this from a one-time cleanup into an invariant,
mirroring phase 2.1's enum↔mesh gate.

## Consequences

Gains: one resolver contract and one envelope a reader learns once; profile/borrador
stop the B→A→B round-trip; counterpart/720 join the live calculate path (closing a
real orphan); retenciones has one path; the four-place enrollment scatter collapses to
one registry with a parity gate. Together with phase 2.1 this delivers the "cohesive,
centralised" resolver half of the bindings engine.

Difficulties, framed honestly: the C-service fold is the highest-risk step (live-path
resolvers for counterpart/720/retenciones must be behaviour-preserving, proven against
the existing suites); folding profile/borrador must preserve the caller-override
precedence exactly; and retiring the vestigial envelopes requires reconciling their
few real consumers first. Execution depends on phase 2.1 and is gated/sequenced behind
it. This ADR is design-ahead and proposed — it asserts no completed change and
requests no acceptance ahead of coordinator review.

Out of scope (later phases): the relation-vs-previous_filing value-layer fold-in dedup
and the one compensación-carry mechanism (phase 2.3); the naming homonyms and CLI verb
fork (phase 2.4); the `MultiYearResolver` orphan deletion (a phase-2.3/code-removal item).

## Codification candidates

- **Rule slug:** `one-source-resolver-contract` (author at phase-2.2 review/codify,
  after it holds through execution — not now).
  **Rule:** A source value is resolved through exactly one port
  (`ModeloSourceResolver`) returning one envelope (`CalculationSourceResolution`); a
  new source enrolls in the single mesh or is recorded in the one disposition registry
  as a documented, test-gated exception — never a parallel result shape or a second
  pipeline — and a parity gate keeps the registry equal to the enrolled set.


