---
tags:
  - '#adr'
  - '#bindings-architecture-unification'
date: '2026-06-26'
modified: '2026-06-26'
related:
  - '[[2026-06-26-bindings-architecture-unification-audit]]'
  - '[[2026-06-26-bindings-architecture-unification-research]]'
  - '[[2026-06-26-binding-source-kind-taxonomy-unification-adr]]'
  - '[[2026-06-14-bindings-interface-hardening-adr]]'
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
  - '[[2026-05-20-calculation-source-connectivity-adr]]'
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]'
---



# `bindings-architecture-unification` adr: `central bindings architecture: one canonical cross-source data-sourcing interface reconciling the source-kind, resolver-contract, fold-in, and carry decisions` | (**status:** `rejected`)

> DEMOTED — the apex approach was declined by the operator ("an apex won't fix it";
> rework the corpus individually). This document is NOT an adopted governing ADR and
> is NOT the canonical home. The canonical direction is the reworked corpus: the PHASE
> ADRs (the phase-2.1 `binding-source-kind-taxonomy-unification` ADR and the future
> phase-2.2/2.3/2.4 ADRs) plus the genuinely FOUNDATIONAL ADRs.
>
> Its analytical content is KEPT as reconciliation ANALYSIS feeding the per-ADR corpus
> rework (`2026-06-26-binding-adr-corpus-reconciliation-plan`): the five axes, the
> C1-C6 adjudications, and the reconciliation ledger below remain valid INPUT, not
> adopted decisions. (The C6 `RowSetGroupingKind` adjudication recorded here as
> "keep-but-derive" was refined at coordinator review to KEEP, NO bridge — see the
> phase-2.1 ADR, which is the canonical record.) The same analysis also lives in
> `2026-06-26-bindings-architecture-unification-research`.
>
> Status note: an earlier revision of this document was self-accepted under a
> `/goal`-as-acceptance-authority reading; that was over-authorization — the operator's
> explicit "no apex" directive governs — and the acceptance is reverted here.

## Problem Statement

This is the APEX / central ADR of the bindings-architecture-unification sweep — the
single canonical home the operator's standing goal calls for: "reconcile all ADRs,
conflicting architecture, and prior decisions and standardise the codebase around a
new central binding ADR, so that every semantic search returns relevant, highly
standardised, cohesive findings that define a clear, well-centralised bindings
architecture." It exists because, until now, NO document owned "the bindings
interface" as a whole — the term "bindings" means, per operator directive, ANY
interface where a calculation sources data cross-modelo or from another storage
vault / source, not the `--binding` CLI flag.

Two grounding documents established the breadth. The code audit
(`2026-06-26-bindings-architecture-unification-audit`) mapped ten code-level
fractures (F1–F10): the source-kind closed set declared four-plus times with a
typed-registry / stringly-typed-mesh split (F1); three unreconciled
sourcing-contract shapes and 4–6 result envelopes (F2); six-plus parallel
"source-a-prior-value" mechanisms with relations and `previous_filing` as two full
implementations of one fold-in (F3); relation aggregation never typed (F4);
enrollment state in four disconnected registries (F5); pervasive naming homonyms
(F6); a forked CLI verb surface (F7); and residual type-erasure (F8–F10). The
decision-corpus research (`2026-06-26-bindings-architecture-unification-research`)
mapped the complementary DOCUMENT fracture: ~20 ADRs touching bindings/sourcing,
six concrete inter-document conflicts (C1–C6), and three empirically-confirmed
RAG-incoherence findings (R1–R3) where a semantic search for a core concept returns
an 8-ADR scatter with no canonical home.

The root cause is singular: the two prior governing ADRs each fenced the other's
territory out of scope. `2026-06-10-calculation-aggregation-taxonomy-adr` settled
the resolver-mesh mechanism ownership; `2026-06-14-bindings-interface-hardening-adr`
hardened the registry-binding definition. Each is internally sound, neither owns the
UNION, and a constellation of older and in-flight ADRs (per-modelo aggregation
pipeline, borrador-100 integration, the IVA-wallet reconciliation, the M303/M390
carry cluster) each introduced a parallel source vocabulary or carry mechanism with
no canonical home to point to. The corpus is RAG-incoherent precisely because no
document points "up." This ADR is that "up."

## Considerations

What this ADR IS. It is the canonical architecture-defining home: it (1) states the
one bindings architecture across all altitudes, (2) ADJUDICATES the six corpus
conflicts with explicit proposed decisions, (3) sequences the four implementation
phases (2.1 source-kind taxonomy, 2.2 resolver-contract unification, 2.3 fold-in /
carry unification, 2.4 vocabulary + CLI cohesion), and (4) declares the
supersession/absorption disposition for every corpus ADR so RAG hops converge here.
It is the parent of the phase ADRs (the first, `binding-source-kind-taxonomy-unification`,
is already authored and proposed).

What this ADR is NOT. It does not re-decide the settled FOUNDATIONS it builds on —
the `ModeloSourceResolver` mesh port (`calculation-source-connectivity`), the
registry validation contract and provenance parity (`bindings-interface-hardening`
clusters A/D), the law-determined revision resolution and the unified R2 carry-trust
gate (`period-revision-resolution`, rule `carried-observations-stamp-their-revision`),
and the conformant Option-C worked examples (M130 direct carry, M353 `per_grupo_member`
fan-in). It links to these; it does not reopen them.

Acceptance and landing authority. This ADR is `proposed`. Its acceptance — and the
acceptance of the supersession dispositions below — is the operator's / coordinator's
decision, not the authoring agent's; the supersession links recorded on the absorbed
ADRs are explicitly marked "proposed, pending acceptance of this ADR." No code lands
on the strength of this document: every code change rides its phase ADR → plan →
review and the report-before-land gate, sequenced around the active casilla-id sweep.
The reconciliation this ADR performs NOW is the DOCUMENT-corpus reconciliation —
which is itself half the goal, because the `.vault/` corpus is a first-class RAG
surface and its incoherence (R1–R3) is exactly what the goal targets.

## Constraints

- **Proposed, not landed.** The architecture is decided here as a proposal; the
  codebase standardisation happens phase by phase under the report-before-land gate.
  This document changes no code and asserts no completed code change.
- **Acceptance is human-gated.** Supersession of an ACCEPTED ADR formally takes
  effect only when this ADR is accepted; until then the `## Status` forward-pointers
  on the absorbed ADRs read "proposed supersession." This avoids asserting a
  reconciliation the human has not ratified.
- **Behaviour-preserving where it touches types.** The source-kind consolidation
  (phase 2.1) is a StrEnum lift with zero stored/compared-string change; the
  fold-in/carry unification (phase 2.3) must preserve every conformant worked
  example and the M303 iva-wallet carve-out semantics.
- **Shared factory branch + active sweep.** Execution of every phase coordinates
  around the casilla-id sweep (task #18) and lands as atomic explicit-path commits
  with docs-scaffold regen, under `full-tree-gate-must-distinguish-owner`.

## Implementation

The central architecture is one canonical answer on each of five axes. Each axis
names the phase that implements it and the conflict(s) it resolves.

**Axis 1 — One source-kind authority (phase 2.1; resolves C1).** The core
`BindingSourceKind` StrEnum is THE single source-kind closed set across BOTH the
registry binding definitions AND the application resolver mesh. The duplicate
`AggregationSourceKind` and `operator_surface.SourceKind` are deleted; the mesh is
re-typed off bare strings; the union gaps close (`borrador`, `iva_wallet_decision`
become members; `purchase_invoice_evidence`, `ledger_transaction` get explicit
disposition). An enum↔mesh parity gate makes "neither set contains the other"
impossible to recur.

**Axis 2 — One resolver contract (phase 2.2; resolves F2, C5).** One port
(`ModeloSourceResolver`) and one result envelope (`CalculationSourceResolution`).
The pre-mesh `BindingSourceResolution` shape (profile, borrador) is either folded
into the mesh or formally documented as a gated exception ending the B→A→B wrap; the
per-modelo aggregation service (the third shape, counterpart/347/349/720) is folded
into the mesh or declared a separate, test-gated, documented surface — not a silent
parallel pipeline. A single "where does source X resolve" disposition registry
(enrolled / pre-mesh / deferred / reserved) plus a frozenset↔enrollment parity gate
replaces the four scattered enrollment structures, making `no-dormant-source-resolvers`
enforceable across the union.

**Axis 3 — One fold-in mechanism per type (phase 2.3; resolves C4).** The Option-C
topology stands (relation = cross-modelo fold-in; `previous_filing` = same-modelo
carry; `per_grupo_member` = cross-member fan-in; iva-wallet = compensación), but the
DUPLICATE VALUE-LAYER IMPLEMENTATION is collapsed: one requirement record (not
`RegistryRelationSourceRequirement` ≈ `RegistryModeloObservationRequirement`), one
observation-fold helper (not three copies), one period-offset implementation, and
relation aggregation lifted onto the typed `BindingAggregation`/op model at parity
with bindings (resolves F4). The aggregation-taxonomy ADR assigned ownership; this
axis completes it by removing the second codepath it left standing.

**Axis 4 — One compensación carry mechanism (phase 2.3; resolves C3).** The IVA
wallet decision is the canonical compensación-carry authority (per the
aggregation-taxonomy Option-C row and the live-wallet ADR); the registry
`previous_filing` formula path and the `derive_303_compensation_available` path are
reconciled to feed or defer to it, disposition-aware, so the refunded-period
zeroing (`m303-carry-reconciliation`, proposed) and the M390 FIFO partition
(`m390-iva-carry-boxes`, proposed) resolve through ONE mechanism rather than three.
This ADR decides the DIRECTION (one wallet-anchored carry authority); the two
proposed carry ADRs become its children and land their mechanics under it.

**Axis 5 — One vocabulary + CLI surface (phase 2.4; resolves F6, F7, C2, C6).** A
naming-discipline pass retires the homonyms (`BindingRow`×4, `Observation`×30+, the
`resolve`/`provider`/`resolution` tangle) and the false-friend filenames, and
reconciles or formally exempts the genuine `*SourceKind` homonyms
(`ModeloReconciliationSourceKind`, `BusinessOperationInvoiceSourceKind`,
`IvaCompensationAuthoritySourceKind`) and the oracle/wallet "binding" name
collisions against rule `binding-names-reserved-for-registry-input`. The CLI verb
fork (pull / preview / calculate) is reconciled under the existing CLI-standard rules.

Adjudication of the open questions. **C6 (`RowSetGroupingKind` absorb vs derive):**
KEEP it a distinct downstream row-assembly axis but bind it as a derived, gated
projection of `BindingSourceKind` (not merged) — it is a different semantic axis, and
`BindingSourceKind` already carries the corresponding source members. **C2 (two
"reconciler" ADRs):** THIS ADR is the authoritative bindings-architecture home; the
`2026-05-22-live-iva-compensation-wallet-...-binding-reconciliation-adr` is scoped to
the wallet/layer-hierarchy concern and becomes a child whose source-kind claims are
absorbed into Axis 1. Both adjudications are proposed, pending acceptance.

## Rationale

The corpus is RAG-incoherent because reconciliation was always deferred to "the
next campaign" and no document ever claimed the union. Every prior ADR is locally
correct; the failure is the absence of a centre. Authoring the centre — and wiring
the older docs to point at it — is therefore the single highest-leverage action for
the operator's goal, because a semantic search converges only when the scattered
docs share a canonical target (research finding R1/R3). Deciding the five axes as
one coherent set (rather than four independent phase ADRs) is necessary because the
axes interlock: the source-kind authority (1) underpins the resolver contract (2)
and the parity gates; the fold-in collapse (3) and the carry authority (4) share the
observation store and the typed aggregation model; and the vocabulary pass (5)
depends on all of them being named first. Each axis is the project's OWN existing
rule applied to the union the rules were only half-enforced across — this is
reconciliation by extension of settled discipline, not a new architecture invented
from scratch.

## Consequences

Gains: a single canonical document that DEFINES the bindings architecture and that
RAG converges on; explicit adjudication of all six corpus conflicts; a sequenced,
gated implementation path; and supersession wiring that makes the older corpus
point "up," directly attacking the R1–R3 incoherence. Once the phases land, the
codebase carries one source-kind authority, one resolver contract, one fold-in
mechanism per type, one compensación-carry authority, and one vocabulary — the
"clear, well-centralised bindings architecture" the goal names.

Difficulties, framed honestly: this ADR DECIDES directions but LANDS nothing — the
standardisation is real only when phases 2.1–2.4 execute, each gated and sequenced
around the active sweep, so the goal is not "done" at acceptance, it is "owned and
sequenced." The supersession dispositions touch many ACCEPTED ADRs and are only
proposals until this ADR is accepted; mislabelling them as effected would assert a
ratification that has not happened. The carry-mechanism adjudication (Axis 4)
intersects in-flight proposed ADRs (#6/#28-adjacent M303/M390 work) and must not
force a re-do of their landed point-fixes — they become children, their fixes
preserved. And the fold-in collapse (Axis 3) is the highest-risk phase: it touches
live calculate-path resolvers and must preserve every conformant worked example and
the M303 carve-out exactly.

Explicitly NOT reopened (foundational, link-only): the mesh port, the registry
validation/provenance contract, revision resolution and the R2 carry-trust gate, and
the M130/M353 worked examples.

## Reconciliation ledger (proposed dispositions)

The disposition of each corpus ADR under this central architecture. "Absorbs-part"
means this ADR's canonical decisions supersede a specific portion (named) of the
older ADR; the older ADR keeps the rest. Proposed, pending acceptance.

- FOUNDATIONAL — link only, not reopened: `calculation-source-connectivity` (mesh
  port); `period-revision-resolution` (revision + R2 carry-trust);
  `modelo-130-pagos-fraccionados-carry`, `modelo-multiyear-renta-353-grupo-aggregation`
  (Option-C worked examples); `t6-aggregation` (ledger→casilla predecessor).
- FOUNDATIONAL + ABSORBS-PART: `bindings-interface-hardening` (Axis 1 extends its
  `BindingSourceKind` registry→union; Axis 3 extends its typed-op to relations);
  `calculation-aggregation-taxonomy` (Axes 3–4 complete its mechanism ownership by
  removing the duplicate value-layer codepath).
- ABSORBS-PART (source vocabulary): `cli-workflow-redesign-per-modelo-aggregation-pipeline`
  (its `AggregationSourceKind` set → Axis 1; its service shape → Axis 2);
  `cli-workflow-redesign-app-modelo-bindings-shape` (`operator_surface.SourceKind` →
  Axis 1; CLI surface → Axis 5); `cli-workflow-redesign-borrador-100-binding-integration`
  (`borrador` source → Axis 1; precedence ladder → Axis 2).
- ABSORBS-PART (carry) → Axis 4: `live-iva-compensation-wallet-...-binding-reconciliation`
  (C2: scoped to wallet/layer-hierarchy, source-kind claims absorbed),
  `live-iva-compensation-wallet`, `iva-compensation-chain`, `m303-cross-period-carry-continuity`,
  `modelo-iva-routing-carry`, `m390-annual-autoconsumo-promotor-source`, and the two
  proposed carry ADRs `m303-carry-reconciliation` + `m390-iva-carry-boxes` (become
  children of the one wallet-anchored carry authority).
- ORTHOGONAL — name-collision only, flagged for Axis 5 vocabulary census, not
  reopened: `cross-reference-oracle-binding` ("binding" = oracle cross-reference);
  `cross-period-calculation-guards`, `cross-period-filing-clean-state` (evidence-gate
  layer).

## Codification candidates

Deferred to each phase's review/codify, NOT promoted now (per `vaultspec-codify`: a
lesson qualifies only after it holds through an execution cycle). The durable
constraints this architecture will codify once its phases land:

- `binding-source-kind-single-taxonomy` — EXTEND registry→registry+mesh end-to-end
  (phase 2.1).
- `binding-aggregation-is-typed` — EXTEND bindings→relations (phase 2.3).
- A one-resolver-contract rule (one port, one envelope; new source enrolls in the
  single mesh or is test-gated-documented as a separate surface) (phase 2.2).
- A one-compensación-carry-authority rule sharpening `calculation-source-canonical-mechanism`
  (phase 2.3 / Axis 4).
- A docs-cohesion discipline: a new ADR that introduces a binding/source vocabulary
  MUST point at this central architecture via `## Status`, so the corpus stays
  RAG-coherent (candidate phase-2.4 codify).


