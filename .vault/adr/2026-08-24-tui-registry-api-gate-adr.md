---
tags:
  - '#adr'
  - '#tui-registry-api-gate'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:4414780fe1ca6a7d46b811d28d2d953e0b791467ca319ea47b275c95dca2e6de'
related:
  - "[[2026-08-24-tui-registry-api-gate-research]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-10-casilla-schema-read-model-adr]]"
---

# `tui-registry-api-gate` adr: `versioned Modelo workspace and operation projection boundary` | (**status:** `proposed`)

## Problem Statement

The accepted Casilla read model and operation platform answer separate bounded
questions, but they do not give a complex Modelo frontend one stable contract
for registry schema, materialized values, capability, refusal, concurrency, and
supervised mutation. Binding a visual cohort directly to registry snapshots,
persistence records, or private application assemblers would make registry
evolution a frontend-breaking concern.

This record establishes a versioned, frontend-neutral application boundary
comprising a Modelo workspace projection and a public operation projection. It
owns their join and stability gate. It does not redefine registry authority,
calculation semantics, operation lifecycle, or TUI information architecture.
The gap and scope are grounded in
`2026-08-24-tui-registry-api-gate-research`.

## Considerations

- Revision selection remains law-determined; authority grade is a capability
  requirement, not an alternate revision selector
  (`2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr`).
- Locale is an explicit projection axis and cannot alter identities, revision
  selection, values, capability, or baseline.
- Complex surfaces need row-addressable materialization and typed causal
  structure, not only scalar casilla summaries
  (`2026-08-24-tui-registry-api-gate-research`).
- Registry closure, source connectivity, and export authority retain their
  owners; the workspace composes their results rather than reproducing them
  (`2026-08-24-registry-completeness-closure-adr`).
- `ModeloWorkReview` remains a bounded pure-read projection
  (`2026-08-10-casilla-schema-read-model-adr`).
- `OperationSupervisor` and its canonical envelope retain lifecycle,
  interaction, cancellation, settlement, and effect authority
  (`2026-08-11-tui-architecture-adr`).
- TUI layout and view models remain under the interface authority; application
  contracts contain no Textual concepts (`2026-08-11-tui-interface-adr`).

## Considered options

- **Grow `ModeloWorkReview` into the complete workspace contract.** Rejected:
  it destroys the bounded review projection and couples existing consumers to
  edit and operation concerns.
- **Let the TUI consume registry snapshots and operation journal records
  directly.** Rejected: it exposes compiler grammar and persistence topology
  and makes frontend code interpret authority and lifecycle.
- **Assemble a TUI-owned workspace from multiple application calls.** Rejected:
  every frontend would repeat the join and invent refresh semantics.
- **Create one application-owned, versioned Modelo workspace projection joined
  by typed references to a public operation projection.** Chosen: registry and
  operation authorities remain separate while the application composes them.

## Constraints

- The workspace and operation projections live behind their owning application
  package facades. Neither exposes private registry modules, persistence DTOs,
  repositories, raw exceptions, frontend types, or untyped payload bags.
- A workspace request explicitly supplies modelo, filing year, period, bucket or
  work identity, required authority grade, output language, and contract version.
- Required grade never chooses a revision. The producer law-selects the revision
  and evaluates the requested grade without silent downgrade.
- Locale affects localized display fields only. Requested language, resolved
  language, and fallback disposition are explicit.
- Every frontend-significant Casilla, binding, relation, formula,
  export-exposure, continuity, and row-materialization field is represented or
  classified backend-only with a reason. An unclassified new field fails the
  coverage gate.
- Boundary models are strict, frozen, and typed. Selectors are discriminated;
  aggregation and source axes retain canonical enums; formula operands and
  relation endpoints retain typed namespaces.
- Financial values and raw source identities never enter operation journals,
  events, diagnostics, baselines, or concurrency tokens. Provenance uses typed
  sources and safe opaque references or fingerprints.
- A workspace baseline is an opaque safe digest, grants no approval, and is
  revalidated immediately before every mutation.
- Contract versions are refusal boundaries, not compatibility layers. Breaking
  changes migrate all in-tree consumers atomically and delete the old version.

## Implementation

### Workspace contract

Introduce a versioned contract family centered on `ModeloWorkspaceRequest`,
`ModeloWorkspaceResult`, `ModeloWorkspaceProjection`, and
`ModeloWorkspaceBaseline`. The result is discriminated: a workspace projection
may honestly carry unavailable capabilities, while unresolved identity,
revision, storage, or authority returns a typed refusal rather than a frontend
exception or localized prose.

The projection carries contract and request identity, law-selected revision,
declared and required authority grades, locale resolution, work and calculation
revision identities, and baseline. It includes complete projected Casilla,
binding, relation, formula, continuity, export, scalar, repeated-row,
materialization, provenance, and causal-graph records. One application assembler
owns the graph; bounded public views may select from it but cannot reconstruct
revision, provenance, capability, or causal edges independently.

`ModeloWorkReview` stays pure-read. Its grade and localization defects are
repaired, and it may reuse the canonical assembler, but it does not gain editing,
operation state, complete registry grammar, concurrency tokens, or commands.

### Authority grade, locale, capability, and refusal

The response echoes the law-selected revision and declared grade. Under-grade
targets expose a typed refusal for the requested capability while retaining any
lower-grade inspection capability the authority can honestly provide. Locale is
resolved through canonical accessors with visible fallback and identity parity.

The workspace composes schema review, calculation, verification, filing-draft,
export, and enrolled-action capabilities from their owning producers. Each is
available, not applicable, refused, or unmeasured. Refusals carry stable code,
affected capability, selected revision, safe facts, evidence references,
responsible disposition, reconsideration condition, and optional canonical
action reference. Registry incompleteness is representable data; an unavailable
capability can never appear enabled.

### Operation projection and mutation enrollment

Expose a versioned frontend-safe projection from the canonical operation
envelope. Journal and persistence models remain private. The projection preserves
operation identity, definition identity, envelope revision, lifecycle, phase,
progress, cursor, pending interaction, cancellation and deadline availability,
close policy, review operand reference, result or refusal, effect, and safe
diagnostic reference.

Workspace actions reference registered operation definitions, never callbacks.
Every Modelo mutation exposed through TUI, CLI, or MCP is registered before a
visual action may invoke it. Requests carry the workspace baseline and domain
identifiers; the executor revalidates the baseline immediately before effect.
Existing domain writers remain the sole effect authorities. Pure workspace reads
and `ModeloWorkReview` remain direct queries.

### Contract versioning and conformance

Workspace and operation projections carry separate schema versions, distinct
from registry revision and operation-definition revision. Conformance proves
strict payload roundtrips; law-selected revision and grade behavior; locale and
fallback parity; scalar and repeated-row materialization; alternate bindings,
relations, formulas, manual and conflicting origins; provenance and causal-edge
parity; current-model projection-field coverage; capability parity; baseline
stability and stale refusal; operation joins; forbidden-import absence; and
non-retention of sensitive values.

### Dependency and sequencing gates

Existing operation backend, persistence, executor, migration, registry, and
bounded review work may continue. Complex Modelo views depending on complete
schema, rows, causal provenance, or capability-driven controls; `modelo.edit`;
and visual mutation paths remain blocked.

The complex read cohort opens only after the authority-grade decision is accepted
or reconciled, workspace contract version 1 is public, current-HEAD conformance is
green, and the TUI dependency receipt records that version and proof. The edit
cohort additionally requires the public operation projection, enrollment of
every exposed Modelo mutation, fixed-point joins, stale-baseline proof, and
secure-operand proof. Global registry completeness is not a prerequisite;
typed evidence-backed refusals are valid. The existing architecture-close and
`EphemeralSecretSubmission` gates remain unchanged.

## Rationale

The application layer alone can join law-selected registry authority, secure
work state, calculation materialization, capability producers, and supervised
operations without reversing dependencies. Separating current workspace state
from in-progress operations preserves their different authorities while typed
identities and baselines create one coherent frontend contract.

Explicit grade and locale remove hidden producer policy. Complete typed causality
prevents the frontend becoming a registry interpreter. Capability composition
lets ongoing registry campaigns surface honest refusals without turning every
content gap into contract instability. This preserves the accepted boundaries
grounded by `2026-08-24-tui-registry-api-gate-research`.

## Consequences

- Complex Modelo views gain one stable target for schema, values, rows,
  causality, capabilities, actions, and concurrency.
- Registry evolution becomes an explicit projection-coverage obligation.
- `ModeloWorkReview` remains small and useful for bounded review consumers.
- Authority insufficiency and registry incompleteness render as typed states
  rather than crashes, unexplained disabled controls, or silent downgrade.
- Every visual mutation shares supervision and settlement semantics with CLI
  and MCP while existing writers retain effect ownership.
- The contract and its current-schema coverage fixtures are substantial and
  evolve whenever frontend-significant registry semantics evolve.
- Complex visual work pauses until projection receipts are real; unrelated
  backend, registry, and bounded review work continues.
