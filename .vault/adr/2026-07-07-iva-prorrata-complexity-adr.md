---
tags:
  - "#adr"
  - "#iva-prorrata-complexity"
date: '2026-07-07'
related:
  - "[[2026-07-07-prorrata-especial-adr]]"
  - "[[2026-07-07-prorrata-sectores-diferenciados-adr]]"
  - "[[2026-07-07-prorrata-art104-tres-exclusions-adr]]"
  - "[[2026-07-07-prorrata-art105-cinco-interrupted-adr]]"
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
  - "[[2026-07-05-cross-period-prorrata-adr]]"
  - "[[2026-07-01-iva-complexity-hardening-scope-adr]]"
  - "[[2026-07-10-iva-prorrata-complexity-research]]"
supersedes:
  - '2026-07-01-iva-complexity-hardening-scope-adr'
modified: '2026-07-17'
---
# `iva-prorrata-complexity` adr: `IVA prorrata complexity: bind the 4 deferred W06 axis decisions into one collision-clustered implementation campaign` | (**status:** `accepted`)

## Problem Statement

The accepted `cross-period-prorrata` ADR shipped prorrata general and explicitly
deferred four complexity axes, each now decided in its own axis-ADR: prorrata
especial (LIVA arts 103.Dos/106), sectores diferenciados (arts 101/9.1.c),
art-104.Tres denominator exclusions, and art-105.Cinco interrupted-activity
seeding. These four must be implemented over a small set of SHARED code surfaces
- the ledger transaction model, the one shared IVA ledger aggregation, the
prorrata register, and the M303 registry - without colliding and without the
version-skew / rebuild-what-exists duplication that a per-axis uncoordinated
build invites. This ADR is the feature-level authority that binds the four
axis-decisions into one sequenced implementation, and is the decision the
implementation plan and its execution records hang from.

## Considerations

- The four axis-ADRs are each self-contained regulated decisions, grounded
  verbatim in the bundled consolidated LIVA. This ADR does not re-decide them; it
  decides how they land together.
- The three ledger-touching axes (especial, sectores, art-104.Tres) all WRITE the
  ledger transaction model and the one shared aggregation; two of them running
  concurrently would collide at the line level. art-105.Cinco is
  register/seeding-internal and touches neither.
- Sectores extends the regime-aware aggregation that especial establishes: a
  logical dependency, not only a collision.
- The compute substrate already carries the primitives (input classification, the
  sectoral predicate, definitiva/regularizacion, the register enums); the axes
  wire and extend, they do not rebuild (RAG-first, no duplication).

## Considered options

**O1 - Four independent per-axis plans, implemented ad hoc (REJECTED).** Each
axis-ADR gets its own plan and lands whenever. Con: the three ledger-touching
axes collide on the shared model/aggregation with no ordering authority, and the
recurring rebuild-what-exists failure is unguarded.

**O2 - One umbrella implementation plan whose Waves are derived from the
ADR-vs-ADR write-file overlap matrix (CHOSEN).** The four axes cluster per-ADR
into Phases; Waves group them so that any two axes sharing a write-file never run
concurrently, and the especial->sectores dependency is honoured. One owner per
Wave.

**O3 - Fold the four axes into the parent cross-period-prorrata plan (REJECTED).**
That plan is closed and product-verified; reopening it conflates the delivered
general mechanism with the deferred complexity tail.

## Constraints

- Parent stability: `cross-period-prorrata` (accepted, product-verified) and the
  `2026-05-12` compute-substrate ADR (accepted) are consumed, not re-opened.
- No fabrication: every regulated rule/figure is grounded verbatim in the bundled
  `ley-37-1992.html`; an unclassified or insufficient case surfaces an advisory,
  never a silent assumed value.
- No collision: the Wave boundaries are the enforcement surface; concurrent Phases
  never share a write-scope (each Step declares its file scope in the plan).

## Implementation

The binding is realised as the L3 plan under this feature. Wave W01 runs
art-104.Tres exclusions in parallel with art-105.Cinco interrupted-activity (they
share only distinct functions in the regularizacion advisory module and distinct
additive legal-catalogue blocks). Wave W02 lands prorrata especial - the
regime-aware per-input apportionment that rewrites the shared ledger aggregation.
Wave W03 lands sectores diferenciados, extending especial's regime-aware
aggregation to per-sector routing. Each axis carries its own AEAT worked-example
verification and, for any new persisted field, a strict roundtrip plus
anti-tautology proof. No per-axis code is decided here; the four axis-ADRs hold
the per-axis design.

## Rationale

Grouping the four deferred axes under one umbrella decision, sequenced by the
empirical write-file overlap matrix rather than by intuition, is what makes the
parallelism provable (only the two non-ledger-colliding axes share a Wave) and
the collision impossible (the ledger-touching axes serialise). It also gives the
feature the single authorising decision the exec/plan chain requires, so every
implementation Step records against an authorising ADR.

## Consequences

- Gain: the four deferred complexity axes implement over the shared ledger and
  register surfaces without collision or duplication, each grounded and
  oracle-verified.
- Gain: one feature-level authority for the plan and its execution records; every
  Step is decision-backed.
- Cost accepted: an extra thin umbrella decision on top of the four axis-ADRs.
- Pathway: completes the IVA prorrata surface the parent ADR opened (general ->
  especial + sectores + full denominator + interrupted seeding).
- Pitfall: a future agent running two ledger-touching axes concurrently would
  collide; the Wave boundaries exist precisely to prevent that and must be
  honoured.
