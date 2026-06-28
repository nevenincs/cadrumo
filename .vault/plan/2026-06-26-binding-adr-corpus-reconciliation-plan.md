---
tags:
  - '#plan'
  - '#binding-adr-corpus-reconciliation'
date: '2026-06-26'
modified: '2026-06-26'
tier: L1
related:
  - '[[2026-06-26-bindings-architecture-unification-research]]'
---


# `binding-adr-corpus-reconciliation` plan

- [x] `S01` - REWORK: re-point the bindings-interface-hardening Status from the apex to the phase ADRs (registry to registry+mesh via phase 2.1; `typed-op to relations via phase 2.3); `.vault/adr/2026-06-14-bindings-interface-hardening-adr.md`.
- [x] `S02` - REWORK: re-point the calculation-aggregation-taxonomy Status from the apex to the phase ADRs (mechanism ownership kept; `value-layer dedup via phase 2.3); `.vault/adr/2026-06-10-calculation-aggregation-taxonomy-adr.md`.
- [x] `S03` - REWORK: note borrador becomes a typed BindingSourceKind member (phase 2.1) and folds into the one resolver contract (phase 2.2); `.vault/adr/2026-05-13-cli-workflow-redesign-borrador-100-binding-integration-adr.md`.
- [x] `S04` - REWORK: keep the bindings CLI surface; `record the operator_surface.SourceKind duplicate as superseded by phase 2.1 and CLI vocabulary aligned in phase 2.4; `.vault/adr/2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr.md`.
- [x] `S05` - REWORK: align the iva-compensation-chain carry grounding to the one wallet-anchored carry authority (phase 2.3); `re-point from the apex; `.vault/adr/2026-05-19-iva-compensation-chain-adr.md`.
- [x] `S06` - REWORK: align the m390-annual-autoconsumo fold-in to the one carry mechanism (phase 2.3); `re-point from the apex; `.vault/adr/2026-06-02-m390-annual-autoconsumo-promotor-source-adr.md`.
- [x] `S07` - REWORK: re-point the m303-carry-reconciliation Status from the apex to the phase ADRs (child of the unified carry authority); `.vault/adr/2026-06-21-m303-carry-reconciliation-adr.md`.
- [x] `S08` - REWORK: re-point the m390-iva-carry-boxes Status from the apex to the phase ADRs (child of the unified carry authority); `.vault/adr/2026-06-21-m390-iva-carry-boxes-adr.md`.
- [x] `S09` - SUPERSEDE: mark the per-modelo-aggregation-pipeline third sourcing shape + AggregationSourceKind superseded by phase 2.1 (enum delete) + phase 2.2 (shape fold); `name the code-removal phases; `.vault/adr/2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr.md`.
- [x] `S10` - SUPERSEDE the binding-reconciler claim (C2) in the wallet-binding-reconciliation ADR; `keep its wallet/layer-hierarchy scope; re-point Status to the phase ADRs; `.vault/adr/2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr.md`.
- [x] `S11` - DEMOTE the apex central ADR: set status to rejected with a note (apex declined by operator; `C1-C6 analysis preserved in the research doc + this plan's verdict table; canonical direction = phase + foundational ADRs); do NOT convert to research; `.vault/adr/2026-06-26-bindings-architecture-unification-adr.md`.
- [x] `S12` - RE-TARGET the 13 cross-campaign Status pointers from the apex to the phase+foundational ADRs per the re-target mapping (source-kind to phase-2.1; `carry to live-iva-compensation-wallet; resolver-contract to calculation-source-connectivity; future phase ADRs named in prose); `.vault/adr/`.
Rework the ~20 binding/sourcing ADRs individually so they coalesce around the phase
ADRs and the foundational ADRs, and supersede the dead or intent-weakening ones.

## Description

The doc-reconciliation track, parallel to the code track (phases 2.1-2.4). Per the
operator's directive: there is NO apex ADR ("an apex won't fix it"); instead the ~20
binding/sourcing ADRs are reworked INDIVIDUALLY so a value-sourcing or carry concept
returns ONE canonical direction, and the ADRs that are dead architecture or weaken
the unified intent are marked superseded. The canonical direction is the NEW PHASE
ADRs (the phase-2.1 `binding-source-kind-taxonomy-unification` ADR + the future
phase-2.2/2.3/2.4 ADRs) plus the genuinely FOUNDATIONAL ADRs; every other ADR aligns
or supersedes AROUND those. Supersession targets a phase or foundational ADR, never a
central apex doc.

This is the report-before-land FIRST deliverable: the coordinator reviews the
KEEP-ALIGN / REWORK / SUPERSEDE verdicts below BEFORE any ADR is edited. The Steps are
the proposed per-ADR `## Status` edits; none execute until the verdicts are approved.
Verdicts are grounded in the decision-corpus reconciliation research (conflicts
C1-C6) and the breadth audit.

Verdict legend: KEEP-ALIGN = foundational, not reopened (at most a one-line language
tweak so it does not contradict the coalesced direction). REWORK = partially
superseded; a `## Status` note records which portion the phase ADR absorbs and points
at it. SUPERSEDE = dead or intent-weakening; a `## Status` block names the superseding
phase/foundational ADR, why it is dead/weakening, and the code-removal phase ref if
the dead architecture still has live code.

### Verdict table

KEEP-ALIGN (foundational - the canonical direction builds on these):
- `2026-05-20-calculation-source-connectivity-adr` - the `ModeloSourceResolver` mesh
  port. Canonical resolver-contract foundation (phase 2.2 builds on it). No edit; it
  is a target, not a subject.
- `2026-06-10-period-revision-resolution-adr` - revision resolution + the R2
  carry-trust gate. Canonical carry-trust foundation. No edit.
- `2026-06-13-modelo-130-pagos-fraccionados-carry-adr` - conformant Option-C direct
  `previous_filing` carry worked example. No edit.
- `2026-06-02-modelo-multiyear-renta-353-grupo-aggregation-adr` - conformant
  `per_grupo_member` fan-in worked example. No edit.
- `2026-04-30-t6-aggregation-adr` - predecessor ledger-to-casilla bridge; historical
  origin of the ledger aggregation resolvers. No edit (note as origin if touched).
- `2026-05-19-live-iva-compensation-wallet-adr` - establishes the AEAT wallet as the
  canonical IVA compensación authority; the ANCHOR of the unified carry mechanism
  (phase 2.3 Axis-4 direction). Language tweak: note it is the carry anchor the carry
  cluster coalesces onto.
- `2026-06-09-modelo-iva-routing-carry-adr` - routing + carry-enrollment + the
  `app_filing` non-official-evidence decision (foundational). Align to the unified
  carry direction.
- `2026-06-03-m303-cross-period-carry-continuity-adr` - the carry-continuity test/gate
  contract. Align (point at the unified carry mechanism).
- `2026-06-05-cross-period-calculation-guards-adr` / `2026-06-05-cross-period-filing-clean-state-adr`
  - the cross-period evidence-gate layer (orthogonal to value sourcing). KEEP-ALIGN.
- `2026-05-06-cross-reference-oracle-binding-adr` - "binding" = live-oracle
  cross-reference, a different concept (name collision only). KEEP-ALIGN; flag for the
  phase-2.4 vocabulary census, do not reopen.

REWORK (partially superseded - the phase ADR absorbs a named portion):
- `2026-06-14-bindings-interface-hardening-adr` - FOUNDATIONAL for the registry
  altitude; phase 2.1 extends its `BindingSourceKind` from registry-only to
  registry+mesh; phase 2.3 extends its typed-aggregation discipline to relations.
  Rework the existing `## Status` to point at the PHASE ADRs (not the held apex).
- `2026-06-10-calculation-aggregation-taxonomy-adr` - FOUNDATIONAL for mechanism
  ownership; phase 2.3 completes it by removing the duplicate relation/`previous_filing`
  value-layer implementation it left standing. Rework the `## Status` to point at the
  phase ADRs.
- `2026-05-13-cli-workflow-redesign-borrador-100-binding-integration-adr` - the
  borrador-as-source decision stands but `borrador` becomes a typed `BindingSourceKind`
  member (phase 2.1) and its precedence folds into the one resolver contract (phase
  2.2). REWORK.
- `2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr` - the
  `bindings list/preview` CLI surface largely stands; the `operator_surface.SourceKind`
  DUPLICATE is deleted by phase 2.1 and the CLI vocabulary aligns in phase 2.4. REWORK
  (keep the CLI surface, supersede the SourceKind duplicate; code-removal phase 2.1).
- `2026-05-19-iva-compensation-chain-adr` - the compensación arithmetic stands; its
  carry grounding aligns to the one wallet-anchored carry authority (phase 2.3).
  REWORK.
- `2026-06-02-m390-annual-autoconsumo-promotor-source-adr` - the M390 annual fold-in
  overlaps the M390 FIFO carry; align to the one carry mechanism (phase 2.3). REWORK.
- `2026-06-21-m303-carry-reconciliation-adr` (proposed) / `2026-06-21-m390-iva-carry-boxes-adr`
  (proposed) - children of the unified carry authority; their `## Status` (already
  added) aligns to the phase ADRs rather than the apex. REWORK (re-point).

SUPERSEDE (dead or intent-weakening):
- `2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr` - defines the
  THIRD sourcing-contract shape (`aggregate_per_modelo`, `AggregationSourceKind`-keyed)
  that never enters the live calculate mesh (counterpart/347/349/720 orphaned). The
  `AggregationSourceKind` enum is deleted by phase 2.1; the parallel shape is folded or
  documented by phase 2.2. SUPERSEDE; target phase-2.1 (source-kind) + phase-2.2
  (resolver contract); code-removal phases 2.1 + 2.2.
- `2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr`
  - intent-weakening (C2): claims to be "the binding reconciler" yet predates and does
  not cover the source-kind union, a competing authority claim. SUPERSEDE the
  reconciler claim (target: the phase ADRs are the canonical binding-vocabulary
  authority); KEEP its wallet/layer-hierarchy scope. The `## Status` already added is
  re-pointed from the apex to the phase ADRs.

Apex DEMOTION (operator confirmed no-apex):
- `2026-06-26-bindings-architecture-unification-adr` (the apex central ADR I authored)
  - the operator declined the apex-as-governing-home. DEMOTE MECHANISM (chosen as the
  cleanest): change its status to `rejected` with a note - "apex approach declined by
  operator; the C1-C6 adjudications + reconciliation ledger are kept as reconciliation
  ANALYSIS feeding the per-ADR corpus rework; the canonical direction is the phase +
  foundational ADRs, not this doc." NOT converted to a research doc, because its
  analytical content (the C1-C6 conflicts + the ADR classification) is ALREADY
  preserved in `2026-06-26-bindings-architecture-unification-research` and in this
  plan's verdict table - so a `rejected`-with-note status loses no analysis and keeps
  the doc readable as the input it was. Reversible if the operator reconsiders.
- The 13 cross-campaign `## Status` forward-pointers currently point at the apex. They
  are RE-TARGETED to the canonical phase + foundational ADRs (NOT the apex). Re-target
  mapping (target = an EXISTING doc; future phase ADRs are named in prose, not
  wiki-linked, until authored): SOURCE-KIND concerns -> the phase-2.1
  `binding-source-kind-taxonomy-unification` ADR. CARRY concerns -> the foundational
  carry anchor `live-iva-compensation-wallet-adr` (+ the future phase-2.3 carry ADR by
  name). RESOLVER-CONTRACT concerns -> the foundational `calculation-source-connectivity`
  mesh-port ADR (+ the future phase-2.2 ADR by name). VOCABULARY/CLI concerns -> named
  for the future phase-2.4 ADR. The two governing foundations
  (`bindings-interface-hardening`, `calculation-aggregation-taxonomy`) re-point at the
  phase ADRs that extend them (2.1, 2.3).

Dead code (no governing ADR, tracked for a code-removal phase): the orphaned
`MultiYearResolver` (no live caller) - delete in a later code phase; not an ADR
subject here.

## Steps







## Parallelization


## Verification
