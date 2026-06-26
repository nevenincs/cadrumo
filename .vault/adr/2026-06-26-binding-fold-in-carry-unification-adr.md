---
tags:
  - '#adr'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-06-26'
related:
  - "[[2026-06-26-bindings-architecture-unification-audit]]"
  - "[[2026-06-26-bindings-architecture-unification-research]]"
  - "[[2026-06-10-calculation-aggregation-taxonomy-adr]]"
  - "[[2026-05-19-live-iva-compensation-wallet-adr]]"
  - "[[2026-06-10-period-revision-resolution-adr]]"
---



# `binding-fold-in-carry-unification` adr: `fold-in and carry unification: one cross-filing fold-in implementation and one compensacion-carry authority` | (**status:** `proposed`)

> PROPOSED — design-ahead for coordinator review, authored while phase-2.1 code is
> gated. NOT self-accepted, NOT a code-execution request; EXECUTION sequences after
> phases 2.1 and 2.2. Phase 2.3 of the bindings-architecture-unification sweep; the
> canonical direction is the phase + foundational ADRs (no apex).

## Problem Statement

Phase 2.3 of the bindings-architecture-unification sweep, grounded in the breadth
audit (findings F3 and F4) and the decision-corpus reconciliation (conflicts C3 and
C4). Phase 2.1 unified the source-kind set and phase 2.2 the resolver contract; phase
2.3 unifies the VALUE LAYER for "fold a prior/other filing forward" — the most
fragmented region of the surface.

Two defects, verified against the audit:

**F3/C4 — relations and `previous_filing` bindings are two full implementations of one
fold-in.** The `2026-06-10-calculation-aggregation-taxonomy-adr` assigned mechanism
OWNERSHIP (relation = cross-modelo fold-in; `previous_filing` = same-modelo carry;
`per_grupo_member` = fan-in; IVA wallet = compensación) but never removed the duplicate
CODEPATH. The audit found: two near-identical requirement records
(`RegistryRelationSourceRequirement` ≈ `RegistryModeloObservationRequirement`), THREE
near-identical copies of the observation-folding loop, duplicated period-offset math,
and two carve-out frozensets bridging the M303 overlap. Six-plus distinct mechanisms
answer "source a value from a prior period/year/filing," and `MultiYearResolver` is a
confirmed ORPHAN (no live caller).

**F4 — relation aggregation never received the typed-op treatment.** `RelationDefinition.aggregation`
is a free-form `Mapping` with the op re-parsed inline at three sites — exactly the
smell the `binding-aggregation-is-typed` rule forbids for bindings, applied to the
binding half and never the relation half.

**C3 — compensación carry has one declared mechanism but three-plus implementations.**
The aggregation-taxonomy ADR names "M303 compensación = the IVA wallet decision," but
`iva-compensation-chain` grounds it in a registry `previous_filing` formula,
`m303-carry-reconciliation` names "TWO mechanisms, neither disposition-aware," and the
wallet path adds a pre-mesh resolver plus a back-door observation injection. Four docs,
four carry surfaces for one value.

The good news (preserved): all these mechanisms already read ONE observation store and
route through ONE unified `revision_carry_outcome` R2 gate
(`2026-06-10-period-revision-resolution-adr`, foundational) — the carry-TRUST layer is
already unified. The fragmentation is in the VALUE layer, which this phase closes.

## Considerations

This ADR builds on the foundations and does not reopen them: the mechanism-OWNERSHIP
table (`calculation-aggregation-taxonomy`, the Option-C topology) and the carry-TRUST
R2 gate (`period-revision-resolution`) stand; the conformant worked examples (M130
direct carry, M353 `per_grupo_member`) are preserved exactly. It completes the
aggregation-taxonomy ADR by removing the second codepath that ADR's ownership decision
left standing.

The load-bearing decisions are (a) which single requirement record + fold helper the
two mechanisms collapse onto, preserving every conformant example and the M303
iva-wallet carve-out semantics; and (b) the one carry authority. For (b) the canonical
anchor is the foundational `live-iva-compensation-wallet-adr` (the AEAT wallet is the
primary compensación authority); the registry `previous_filing` formula and the
`derive_303` path are reconciled to FEED or DEFER to that one authority,
disposition-aware, so the refunded-period zeroing (`m303-carry-reconciliation`) and the
M390 FIFO partition (`m390-iva-carry-boxes`) resolve through ONE mechanism. Those two
proposed carry ADRs become children of this one authority.

Project rules binding this: `calculation-source-canonical-mechanism` (one mechanism
per type — this phase enforces it by eliminating the duplicate codepath, not only
declaring ownership), `binding-aggregation-is-typed` (EXTENDED to relations here),
`relation-slot-bindings-declare-relation-source` (the relation/`previous_filing`
collision gate — preserved), `carried-observations-stamp-their-revision` and
`revision-resolution-is-law-determined` (the R2 carry-trust layer — not reopened),
`no-dormant-source-resolvers` (the `MultiYearResolver` orphan is deleted), and
`no-legacy-compatibility` (delete the duplicate implementation, do not bridge).

## Constraints

- **Highest correctness risk of the campaign.** This phase touches the live
  calculate-path value layer for cross-filing fold-ins and compensación carry — the
  exact surface that produced multiple prior correctness defects (the M100←M130
  partial-year, M390 box 97/662, M303 refunded-period). Every collapse is
  behaviour-preserving and proven against the existing full-calc / continuity / oracle
  suites; NO casilla value may shift. The #6/#28 perceptor-count result and the M390
  FIFO partition just landed must be preserved exactly.
- **Depends on phases 2.1 + 2.2.** The typed relation aggregation rides phase 2.1's
  `BindingAggregationOp`; the one fold helper lives in the phase-2.2 resolver contract.
  Execution sequences after both; this ADR is design-ahead and lands no code.
- **Preserve the M303 iva-wallet carve-out and the collision gate.** The single
  documented relation/`previous_filing` overlap (`modelo-303-compensacion-pendiente-anteriores`)
  and the `relation-slot-bindings-declare-relation-source` collision gate stay intact;
  the dedup must not collapse the carve-out into a double-fire.
- **Do not reopen the R2 carry-trust layer.** `revision_carry_outcome`, the stamped-revision
  re-confirmation, and the cross-period clean-state evidence gate are foundational and
  unchanged; this phase unifies the VALUE layer beneath them, not the trust layer.

## Implementation

One fold-in implementation, one typed relation aggregation, one carry authority,
orphan deleted. Layering (the plan sequences the steps):

1. **One requirement record + one observation-fold helper.** Collapse
   `RegistryRelationSourceRequirement` and `RegistryModeloObservationRequirement` onto
   one typed requirement model, and the three near-identical observation-folding loops
   (relation, relation-prefill, previous_filing) onto one helper, with one
   period-offset implementation. The Option-C topology (which mechanism OWNS which
   fold) is unchanged; only the duplicated value-layer code collapses. The M353
   `per_grupo_member` fan-in and the M130 direct carry are preserved as the conformant
   shapes the one helper must still produce.

2. **Type relation aggregation (extend `binding-aggregation-is-typed` to relations).**
   `RelationDefinition.aggregation` becomes the typed `BindingAggregation` + `BindingAggregationOp`
   model (phase 2.1's enum); the three inline `str(...).get("op")` re-parses are
   replaced by the one `binding_aggregation_op` accessor, validated at registry-build.

3. **One compensación-carry authority.** The foundational `live-iva-compensation-wallet-adr`
   wallet decision is THE carry authority; the registry `previous_filing` formula path
   and the `derive_303_compensation_available` path are reconciled to feed or defer to
   it, disposition-aware, so a refunded period zeroes its carry-forward once and the
   M390 box-97/662 FIFO partition derives from the one projection. The two proposed
   carry ADRs (`m303-carry-reconciliation`, `m390-iva-carry-boxes`) land their mechanics
   as children under this authority; the back-door observation-injection second route is
   removed.

4. **Delete the `MultiYearResolver` orphan** (no live caller, per `no-dormant-source-resolvers`),
   separating it cleanly from the heavily-live `EnrollmentRecorder` that shares its
   module file; the intended M200-BIN / M303-prorrata consumers, when built, use the one
   fold helper.

A `{reference}` document will pin the concrete anchors (the two requirement records,
the three fold loops, the carry paths, the orphan) the plan edits.

## Rationale

The aggregation-taxonomy ADR did the hard conceptual work (which mechanism owns which
fold); it stopped at declaring ownership and left two implementations standing, so the
fragmentation the audit found (duplicate records, three fold loops, untyped relation
op, four carry surfaces) is unfinished business, not a new problem. Collapsing to one
implementation is `calculation-source-canonical-mechanism` enforced by code, not just
by declaration, and typing the relation op is `binding-aggregation-is-typed` applied to
the half it skipped. Anchoring carry on the wallet (rather than inventing a new home)
respects the foundational decision while ending the three-way drift. Deleting the
orphan is `no-dormant-source-resolvers`. The carry-TRUST layer is already unified, so
this phase is purely the value-layer completion.

## Consequences

Gains: one implementation a reader learns once for "fold a prior filing forward"; one
typed relation aggregation at parity with bindings; one compensación-carry authority so
a value-sourcing/carry concept returns a single answer in code as it now does in the
docs; the orphan gone. With phases 2.1 and 2.2 this delivers the value-sourcing core of
the cohesive bindings engine.

Difficulties, framed honestly: this is the highest-correctness-risk phase — it edits
the live calc value layer that has historically harboured under-declaration defects, so
behaviour-preservation must be proven against the full-calc/continuity/oracle suites,
not asserted. The M303 carve-out and the collision gate must survive the dedup. The
carry reconciliation intersects in-flight proposed ADRs (#6/#28-adjacent) and must
preserve their landed results. Execution depends on phases 2.1 + 2.2 and is sequenced
behind them; this ADR is design-ahead and proposed — no completed change, no acceptance
ahead of coordinator review.

Out of scope: the naming homonyms and CLI verb fork (phase 2.4).

## Codification candidates

- **Rule slug:** `one-fold-in-implementation` (author at phase-2.3 review/codify, after
  it holds through execution — not now).
  **Rule:** "Fold a prior/other filing forward" has one value-layer implementation (one
  requirement record, one observation-fold helper, one period-offset), one typed
  relation aggregation at parity with bindings, and one compensación-carry authority
  anchored on the wallet decision; a new fold-in enrolls under the existing mechanism,
  never a second codepath.


