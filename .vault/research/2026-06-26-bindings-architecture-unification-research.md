---
tags:
  - '#research'
  - '#bindings-architecture-unification'
date: '2026-06-26'
modified: '2026-06-26'
related:
  - '[[2026-06-26-bindings-architecture-unification-audit]]'
  - '[[2026-06-26-binding-source-kind-taxonomy-unification-adr]]'
  - '[[2026-06-14-bindings-interface-hardening-adr]]'
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
---



# `bindings-architecture-unification` research: `decision-corpus reconciliation map: prior bindings ADRs and rules to absorb, supersede, or align under one central architecture`

The complement to the breadth audit (`2026-06-26-bindings-architecture-unification-audit`).
That audit mapped the CODE fragmentation; this maps the DECISION-CORPUS
fragmentation — every prior ADR and rule the eventual central binding architecture
must absorb, supersede, align with, or leave alone, and the places where the
documents themselves describe the same concept inconsistently. The operator's
standing goal is one cohesive, centralised bindings architecture such that semantic
search returns standardised, non-contradictory findings; the document corpus is
itself a RAG surface, so reconciling the docs (not only the code) is half the goal.

Method: a read-only discovery pass over `.vault/adr/` and the rule corpus, using the
vault RAG (`--type vault`) plus direct reads of each relevant ADR's Problem /
Decision / Consequences, classified against the central architecture the phase-2.x
sweep is building. Confidence HIGH unless flagged. Inventory to re-confirm at the
point of any action, per the swarm-audit cadence.

## Findings

### Headline: the unification is already a four-phase family, and the corpus is ~20 ADRs deep

The phase-2.1 ADR (`2026-06-26-binding-source-kind-taxonomy-unification-adr`,
proposed) scopes itself as the FIRST of a four-phase sweep rooted in the breadth
audit: 2.1 source-kind taxonomy union; 2.2 sourcing-contract / result-envelope
unification (audit F2); 2.3 relations-vs-`previous_filing` fold-in duplication
(audit F3); 2.4 naming homonyms + CLI verb fork (audit F6). "The central binding
ADR" is therefore best realised as EITHER the phase-2.x family under the breadth
audit, OR a future APEX ADR that sits above phases 2.1–2.4 and carries the
supersession links that make the corpus RAG-coherent. The single highest-leverage
cohesion action (see RAG-incoherence below) is that apex supersession wiring.

### ADR inventory and classification (relative to the central architecture)

FOUNDATIONAL — build on, do NOT reopen (link only):
- `2026-05-20-calculation-source-connectivity-adr` (the `ModeloSourceResolver` mesh
  port itself).
- `2026-06-10-period-revision-resolution-adr` + rule `carried-observations-stamp-their-revision`
  + rule `revision-resolution-is-law-determined` (the carry-TRUST layer — already
  unified; the 3-copy R2 gate merge is complete).
- `2026-06-13-modelo-130-pagos-fraccionados-carry-adr` and
  `2026-06-02-modelo-multiyear-renta-353-grupo-aggregation-adr` (conformant worked
  examples of the Option-C topology: direct `previous_filing` carry; `per_grupo_member`
  fan-in).
- `2026-04-30-t6-aggregation-adr` (predecessor ledger→casilla bridge).

FOUNDATIONAL-BUT-PARTIALLY-SUPERSEDED (central ADR extends/absorbs part):
- `2026-06-14-bindings-interface-hardening-adr` — canonical at the REGISTRY altitude;
  phase 2.1 extends its `BindingSourceKind` from registry-only to registry+mesh
  union; its typed-op discipline (rule `binding-aggregation-is-typed`) was never
  applied to relations (audit F4).
- `2026-06-10-calculation-aggregation-taxonomy-adr` — canonical for mechanism
  OWNERSHIP (Option C: relation = cross-modelo, `previous_filing` = same-modelo carry,
  `per_grupo_member` = fan-in, IVA wallet = compensación), but it ASSIGNED ownership
  without REMOVING the duplicate relation/`previous_filing` codepath; phase 2.3 must
  supersede the duplicated value-layer implementation.

CONFLICTING / PARTIALLY-SUPERSEDED (introduce parallel source vocabularies or carry
mechanisms the central ADR must adjudicate):
- `2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr` — defines the
  THIRD sourcing-contract shape (`aggregate_per_modelo`, `AggregationSourceKind`-keyed),
  reachable only by the CLI `aggregate` verb; counterpart/347/349/720 never enter the
  live calculate mesh (audit F2 shape C). Phase 2.2.
- `2026-05-13-cli-workflow-redesign-borrador-100-binding-integration-adr` — `borrador`
  is a mesh-only source string with no `BindingSourceKind` member, run outside the mesh
  via the pre-mesh `BindingSourceResolution` path. Phase 2.1 adds the member; phase 2.2
  reconciles its parallel precedence ladder.
- `2026-05-19-live-iva-compensation-wallet-adr` + `2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr`
  — `iva_wallet_decision` mesh-only source + a bespoke pre-mesh resolver + a back-door
  observation injection; and the 05-22 ADR itself claims to be "the binding-vocabulary
  reconciler" yet predates and does not cover the source-kind union (conflict C2 below).
- `2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr` — introduced the
  duplicate `operator_surface.SourceKind`; CLI bindings surface is phase 2.4.
- The carry cluster: `2026-06-21-m303-carry-reconciliation-adr` (proposed),
  `2026-06-21-m390-iva-carry-boxes-adr` (proposed),
  `2026-06-02-m390-annual-autoconsumo-promotor-source-adr`,
  `2026-05-19-iva-compensation-chain-adr`, `2026-06-03-m303-cross-period-carry-continuity-adr`,
  `2026-06-09-modelo-iva-routing-carry-adr` — multiple authoritative carry surfaces
  for one value (conflict C3 below).

ORTHOGONAL (touches "binding"/sourcing but separable; leave alone, flag in phase-2.4
vocabulary census):
- `2026-05-06-cross-reference-oracle-binding-adr` ("binding" = live-oracle
  cross-reference, a name collision with the registry-data-input concept — tension with
  rule `binding-names-reserved-for-registry-input`).
- `2026-06-05-cross-period-calculation-guards-adr` / `2026-06-05-cross-period-filing-clean-state-adr`
  (the evidence-gate layer; grounded by `cross-period-suppression-grounded-in-registry-classification`).

### Rule disposition

- EXTEND (rule body must widen): `binding-source-kind-single-taxonomy` (registry →
  registry+mesh end-to-end); `binding-aggregation-is-typed` (bindings → relations too,
  audit F4); `no-dormant-source-resolvers` (the enum↔mesh parity gate must keep every
  member routed/deferred — today enrollment state is scattered across 4 structures with
  no parity gate, audit F5).
- SUBSUMES-target (the unified mechanism table centralises it; enforce by ELIMINATING
  the duplicate codepath, not only declaring ownership): `calculation-source-canonical-mechanism`.
- KEEP-AS-IS (settled, the central ADR links not reopens): `binding-validation-single-contract`,
  `binding-values-carry-provenance`, `binding-validation`, `relation-slot-bindings-declare-relation-source`,
  `one-aggregation-path-pull-equals-calculate`, `registry-resolver-family-extraction`,
  `carried-observations-stamp-their-revision`, `revision-resolution-is-law-determined`,
  `cross-period-suppression-grounded-in-registry-classification`, `aeat-calculation-grounding`.
- TENSIONS-WITH (vocabulary census must reconcile or formally exempt):
  `binding-names-reserved-for-registry-input` vs the oracle/wallet "binding" ADRs.

### Conflicts and tensions the central ADR must adjudicate

- **C1 — source-kind taxonomy described in ≥4 incompatible vocabularies** across the
  hardening, per-modelo-aggregation-pipeline, app-modelo-bindings-shape, borrador-100,
  and wallet ADRs. Phase 2.1 adjudicates this directly (its whole mandate).
- **C2 — two ADRs each claim to be "the binding reconciler"**: the 05-22 wallet
  reconciliation ADR ("one binding vocabulary and one hierarchy") vs the phase-2.1
  taxonomy-unification ADR. The central ADR must declare which is authoritative for
  SOURCE-KIND vocabulary (taxonomy-unification) vs LAYER/HIERARCHY vocabulary (05-22),
  with a supersession/scope link.
- **C3 — compensación carry: one canonical mechanism declared, three+ implemented.**
  Aggregation-taxonomy says "M303 compensación = the IVA wallet decision," but
  iva-compensation-chain grounds it in a registry `previous_filing` formula,
  m303-carry-reconciliation (proposed) names "TWO mechanisms, neither disposition-aware,"
  and the wallet ADR adds a pre-mesh resolver + back-door injection. The central ADR
  (or phase 2.3) must pick ONE authoritative carry mechanism.
- **C4 — relation vs `previous_filing`: two full implementations of one fold-in**
  (audit F3): duplicate requirement records, three observation-fold copies, duplicated
  offset math, two carve-out frozensets; M390 carry expressed two incompatible ways
  (independent sums vs FIFO partition) across two ADRs. Phase 2.3.
- **C5 — enrollment state has no single registry** (audit F5): enrolled / pre-mesh /
  deferred / service-only tracked in 4 disconnected structures with no parity gate, so
  `no-dormant-source-resolvers` is declared but unenforceable across the union.
- **C6 — `RowSetGroupingKind` absorb-vs-keep-derived** (the open flagged divergence in
  the phase-2.1 ADR): the audit/brief say absorb; the ADR argues keep-but-derive
  (different semantic axis). The central architecture must resolve this explicitly.

### RAG-incoherence findings (empirically observed via `--type vault` search)

- **R1 — "how is a value sourced from another modelo / prior filing"** returns a flat
  scatter of 8+ ADRs with no canonical top hit; no single doc DEFINES the
  cross-modelo-sourcing concept — it is spread across the relation, carry, clean-state,
  and compensación ADRs. This is the core incoherence the goal targets.
- **R2 — "source-kind taxonomy closed set"** surfaces the proposed phase-2.1 ADR and
  the registry-only hardening ADR, but NOT the per-modelo-aggregation-pipeline /
  borrador-100 / wallet ADRs that hold the competing mesh-string vocabulary — a reader
  cannot discover the competing closed set. Resolves only once phase 2.1 lands WITH
  supersession links.
- **R3 — "compensación carry / wallet"** is split across seven docs (three proposed),
  each describing a different mechanism as authoritative; no canonical home.

### Recommendation for the central architecture

1. **Supersession wiring is the highest-leverage cohesion action.** Whether realised as
   an apex ADR above phases 2.1–2.4 or as `## Status` blocks on each phase ADR, the
   central architecture must add explicit supersession/scope links from the canonical
   home INTO every doc it absorbs (the source-kind portions of per-modelo-aggregation-pipeline,
   borrador-100, wallet, app-modelo-bindings-shape; the value-layer implementation of
   aggregation-taxonomy; the carry cluster) so RAG hops converge on one home. R1/R3 stay
   incoherent precisely because no older doc points "up."
2. **Decide the two open questions:** C6 (`RowSetGroupingKind` absorb vs derive) and C3
   (the single canonical compensación carry mechanism).
3. **Install a single "where does source X resolve" registry + parity gate** (C5) so
   `no-dormant-source-resolvers` is enforceable across the union.
4. **Extend two rules in place** so the rule layer (also a RAG surface) matches the
   code: `binding-source-kind-single-taxonomy` and `binding-aggregation-is-typed`.
5. **Sequence holds:** phase 2.1 (source-kind set) is correctly first because every
   later phase references it; but the corpus stays RAG-incoherent until phases 2.2–2.4
   land WITH their supersession blocks. This argues for treating supersession wiring as
   a first-class deliverable of every phase, not an afterthought.

### Scope and gate note

This is read-only campaign-level grounding produced while phase-2.1's plan is held at
the report-before-land review gate. It opens no phase-2.2/2.3/2.4 ADR or plan and lands
no code; it exists to ground the eventual central architecture decision and to give the
coordinator the full reconciliation picture for sequencing.
