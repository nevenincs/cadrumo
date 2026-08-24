---
tags:
  - '#adr'
  - '#tui-registry-api-gate'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:2a452e075cc80817857e3ef6cf4b3cb02659389fa90c4fe82016fefb80ed3e51'
related:
  - '[[2026-08-24-tui-registry-api-gate-research]]'
  - '[[2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit]]'
  - '[[2026-08-11-tui-architecture-adr]]'
  - '[[2026-08-11-tui-interface-adr]]'
  - '[[2026-08-10-casilla-schema-read-model-adr]]'
  - '[[2026-08-10-casilla-schema-canonical-derivations-adr]]'
  - '[[2026-08-10-casilla-schema-blocker-spine-adr]]'
  - '[[2026-06-04-modelo-addressing-ux-adr]]'
  - '[[2026-06-10-period-revision-resolution-adr]]'
  - '[[2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr]]'
  - '[[2026-08-24-registry-completeness-closure-adr]]'
  - '[[2026-08-22-source-casilla-integration-adr]]'
  - '[[2026-08-04-modelo-localization-cascade-adr]]'
  - '[[2026-08-09-cli-action-envelope-hardening-adr]]'
  - '[[2026-08-24-tui-operation-observation-adr]]'
  - '[[2026-08-24-tui-modelo-workspace-interface-adr]]'
---

# `tui-registry-api-gate` adr: `read-only Modelo workspace projection and capability facade` | (**status:** `proposed`)

## Problem Statement

The accepted bounded Casilla review model is sufficient for its existing
read-only screen, but it is not a stable, coverage-proven contract for a complex
Modelo workspace. Direct frontend use of registry snapshots, secure persistence
records, development-only closure joins, or private assemblers would make the
frontend interpret authority and would turn registry evolution into an
untracked interface change.

This record establishes only a versioned, frontend-neutral, read-only
`ModeloWorkspaceProjection` V1 and its capability/refusal facade. It does not
own operation observation, mutation commands, editing, persistence, TUI
information architecture, or visual composition. The evidence and ownership
reconciliation are grounded in `2026-08-24-tui-registry-api-gate-research` and
`2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit`.

## Considerations

- Natural Modelo work addressing and law-determined revision selection are
  accepted authorities; a workspace is their consumer, not a new selector
  (`2026-06-04-modelo-addressing-ux-adr` and
  `2026-06-10-period-revision-resolution-adr`).
- Static revision inspection and a grade-admitted snapshot make different
  authority claims and cannot be represented as one degraded result
  (`2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr`).
- Modelo readiness, registry closure, source connectivity, export proof,
  blocker classification, and recovery action identity already have canonical
  producers. Workspace capability must project those answers without
  recomputing them.
- Complex read surfaces require scalar and repeated-row materialization plus
  typed source lineage, while retaining the accepted row and provenance
  identities (`2026-08-22-source-casilla-integration-adr`).
- Schema is language-neutral. Display text is resolved through the canonical
  localization cascade and locale changes cannot alter domain identity,
  values, or capability (`2026-08-04-modelo-localization-cascade-adr`).
- `ModeloWorkReview` remains a bounded pure-read projection; Workspace V1 is a
  separate, wider read model rather than its replacement
  (`2026-08-10-casilla-schema-read-model-adr`).
- Public operation observation is the external amendment proposed by
  `2026-08-24-tui-operation-observation-adr`. Modelo workspace presentation and
  editing are the external interface/write-side amendment proposed by
  `2026-08-24-tui-modelo-workspace-interface-adr`. Neither proposed record is
  accepted or implemented merely because Workspace V1 exists.

## Considered options

- **Grow `ModeloWorkReview` into the workspace contract.** Rejected because it
  would destroy a deliberately bounded projection and destabilize existing
  consumers.
- **Expose registry snapshots or development reports to frontends.** Rejected
  because it leaks compiler grammar and makes presentation code interpret
  authority, applicability, and evidence.
- **Let each frontend assemble schema, values, readiness, and closure.**
  Rejected because it creates multiple joins, refresh rules, and capability
  truths.
- **Combine read state, operation observation, and editing in one workspace
  contract.** Rejected because those concerns have different lifecycle,
  persistence, and decision owners.
- **Create one application-owned read-only Workspace V1 with typed admission,
  capability, refusal, and baseline-consistent facets.** Chosen because it
  gives complex readers one stable boundary while every underlying authority
  retains its single home.

## Constraints

- Workspace V1 lives behind the public `cadrumo.application.modelo` facade. It
  exposes no private registry model, repository, persistence DTO, raw
  exception, frontend type, callback, command request, or untyped payload bag.
- A request uses the existing discriminated `ModeloVisibleFilingTarget` or
  `ModeloExactWorkUnitTarget`. The visible target is active bucket or explicit
  bucket plus Modelo, filing year, and period. An exact work-unit target is an
  advanced address whose optional bucket assertion must agree with the stored
  work unit. A missing exact target or multiple active natural matches refuse.
  Zero natural matches yield an explicit absent-work read state; the workspace
  never creates or selects a work unit.
- The request separately chooses `static_inspection` or `graded_snapshot`
  admission. Static inspection is not an authority grade and cannot calculate,
  draft, export, or expose materialized work values. Graded admission names one
  required `RegistryAuthorityGrade`; the law-selected revision either satisfies
  it or the result refuses without downgrade.
- A stored, explicit, or work-unit revision is assertion evidence only. The
  producer always selects from Modelo, filing year, and period and reports a
  mismatch rather than resolving through the stored id.
- Every capability answer is copied from its canonical public producer with
  its coordinate and evidence. Absence of a producer or measurement is
  `unmeasured`, never available. Workspace V1 does not infer readiness from
  schema population, layout presence, lifecycle state, or neighbouring
  capabilities.
- Locale affects display fields only. The canonical locale resolver supplies
  the key, requested language, resolved language, and fallback or suppression
  disposition. The workspace never reads schema-carried prose, constructs
  locale keys, or falls from one non-Spanish locale to another.
- Boundary models are strict, frozen, discriminated, and typed. Casilla,
  binding, formula operand, relation endpoint, aggregation, source, row, and
  provenance identities retain their canonical namespaces.
- Financial values, raw secret material, and unsafe source identities never
  enter baselines, refusal facts, diagnostics, field-classification manifests,
  or locale metadata. Safe provenance retains only the canonical typed roles
  and approved opaque references or fingerprints.
- A workspace baseline is a safe opaque consistency token, not approval,
  authorization, a mutation precondition, or a persistence identity.
- V1 is the sole supported in-tree workspace version. Missing, unknown, old, or
  future versions return a typed version refusal. A breaking change migrates
  all in-tree consumers atomically and deletes the retired contract; no dual
  reader or compatibility projection remains.

## Implementation

### V1 request, admission, and result

Introduce a minimal version-dispatch envelope plus the strict
`ModeloWorkspaceRequest`, `ModeloWorkspaceResult`,
`ModeloWorkspaceProjection`, `ModeloWorkspaceRefusal`, and
`ModeloWorkspaceBaseline` V1 models. A successful V1 parse and every
coordinate-bearing V1 result carry `contract_version = 1`. The dispatcher reads
only the declared version before constructing a V1 request, so an unsupported
version can refuse without parsing a target or touching secure state. The V1
request contains one canonical work target, one explicit admission request, and
one output language. It contains no revision selector or calculation-revision
selector; `ModeloVisibleFilingTarget.registry_revision_id`, when present,
remains an equality assertion.

After version validation, the result resolves the target and law coordinate,
then discriminates:

- `static_inspection` carries only the validated static registry projection and
  explicitly records that no snapshot was admitted;
- `graded_snapshot` carries the requested, declared, and effective grade plus
  the exact admitted snapshot scope; or
- `refused` carries the failed boundary without a partial snapshot disguised as
  success.

Every coordinate-bearing result after version validation echoes Modelo, filing
year, period, resolved bucket and work state, law-selected revision,
stored-revision assertion outcome, admission kind, review status, evidence
horizon, family dispositions, contract version, field-classification digest,
canonical registry schema identity and fingerprint, locale summary, and
baseline when a projection was assembled. An absent work unit is explicit read
state; the facade never creates one.

### Schema, materialization, and provenance projection

Workspace schema records are explanatory application DTOs. They preserve the
canonical Casilla, binding, relation, formula, parameter, continuity, export
exposure, applicability, constraint, legal, and source-reference identities
needed by a reader without exporting registry compiler objects or selectors.

Scalar values remain keyed by `CasillaId`. Repeated materialization preserves
the canonical binding or projection identity and positive row index as separate
typed coordinates; it never flattens a row into a synthetic scalar id. Formula
operands and relation endpoints retain their discriminated namespaces.
Provenance is projected from the canonical calculation-source graph: resolved
source, contributor source, `PRIMARY` or `CONTRIBUTOR` role, safe source
reference, fingerprint, and parent reference. The assembler may select and
redact those records but cannot synthesize an alternate owner, edge, identity,
or causal graph.

### Generated field-classification denominator

One generated manifest recursively derives the complete registry
model-and-field universe from the current validated public schema types,
including nested types, discriminated variants, and collection element types.
Every reachable leaf field path and variant branch is classified exactly once
as `projected`, `derived`, or `backend_only`. A projected row names its
Workspace V1 destination; a derived row names its canonical producer and
derivation; a backend-only row names its owner and bounded reason. Counts,
hand-maintained field lists, and permanent allowlists are not denominators.

The fixed-point gate independently regenerates the manifest and refuses an
unclassified, duplicate, stale, or missing field path. The manifest is
conformance evidence, not runtime registry authority, and it never causes a
backend-only field to enter the public payload.

### Canonical capability and refusal facade

Workspace V1 reports the closed read-only capability set for schema inspection,
calculation materialization, verification readiness, filing-draft readiness,
and filing-export readiness. Each record is `available`, `not_applicable`,
`refused`, or `unmeasured` and carries the exact target and revision coordinate,
canonical producer identity, safe evidence references, and source disposition.

Modelo readiness is selected from the canonical
`ProjectionModeloReadiness`; registry completeness is selected from the
canonical cross-authority closure report and its temporal, source-connectivity,
and filing-export limbs. Blockers retain their native code and total
`OperatorActionAxis` projection. An optional recovery `ActionReference` is
copied from the action catalogue; it is guidance only and grants no invocation
authority. If a canonical production producer or join has not landed, the
workspace reports `unmeasured` and never recreates a development-only join.

A domain refusal contains a stable code, affected capability or admission
boundary, requested coordinate, selected coordinate when resolution reached
one, safe typed facts, canonical evidence references, responsible
owner/disposition, reconsideration condition, and optional canonical action
reference. The pre-parse version refusal remains the minimal version-only arm.
Localized command prose and raw exceptions never enter either arm. Global
registry completeness need not be satisfied for Workspace V1 to render; an
evidence-backed refusal is valid workspace data.

### Locale and consistency boundary

Each localized field carries its canonical key plus requested language,
resolved language, and exact resolution disposition. Required Spanish absence
refuses; a non-Spanish miss may use only the canonical Spanish fallback. The
same semantic record has identical identities, values, provenance, and
capabilities in every locale.

`ModeloWorkspaceProjection` is one logical point-in-time read, and the
application owns its complete semantic join. The producer captures a consistency
vector from every canonical registry, work, calculation, readiness, closure,
locale-catalogue, and field-manifest owner contributing to that result, then
mints one safe opaque `ModeloWorkspaceBaseline`. A full response is assembled
against that vector. Every collection without an authoritative finite bound is
delivered through a typed bounded facet, page, or expansion. Those delivery
shapes carry the same contract version, schema identity and fingerprint,
selected revision, and baseline, and are served only while every owner stamp
still agrees. Unpinned pagination is forbidden. A change during assembly causes
a bounded retry or typed `workspace_changed` refusal; it never yields a
mixed-epoch graph. The token contains no raw value, secret, source identity, or
reusable authorization.

### Version and conformance gate

The facade accepts exactly Workspace V1. A V1 success or domain refusal echoes
`contract_version = 1`; a version refusal echoes the requested version and the
sole supported version without presenting the rejected payload as V1.
Unsupported versions refuse before target or secure-state resolution.
Conformance proves strict round trips; visible and exact address parity;
ambiguity and revision-assertion refusal; inspection-versus-snapshot
separation; grade and family-disposition parity; locale resolution; schema and
manifest fixed point; schema-identity and fingerprint parity; scalar and
repeated-row coordinates; provenance edges; readiness and closure parity;
full-versus-faceted baseline consistency; stale and mid-read refusal; version
refusal; forbidden imports; and sensitive-data non-retention.

### C2 complex-read gate and external prerequisites

Existing bounded `ModeloWorkReview` and backend campaigns may continue. The C2
complex-read cohort remains blocked until all of these receipts exist:

1. this ADR is accepted and Workspace V1 is exported from the public
   application facade;
2. for a TUI consumer, `2026-08-24-tui-modelo-workspace-interface-adr` is
   accepted and its C1 exit receipt is green; that record retains ownership
   of destinations, view models, bounded rendering, and visual conformance;
3. the authority-grade decision is accepted or formally reconciled and both
   admission paths use its public contracts;
4. canonical readiness and closure producers are public and their Workspace
   parity tests are green, although individual revisions may still carry
   evidence-backed refusals;
5. the generated current-HEAD field-classification manifest has zero
   unclassified paths and its digest is recorded;
6. the complete V1 conformance suite above is green; and
7. the TUI dependency receipt records source ancestry, Workspace V1, the
   manifest digest, baseline/locale proof, and the exact complex-read routes it
   opens.

C2 authorizes only complex read-only workspace consumers. It does not create
`modelo.edit`, authorize a command, enroll an operation, or open verify, file,
export, amendment, lifecycle, secret, or recovery interactions. Public
operation observation is external to this record through
`2026-08-24-tui-operation-observation-adr`. Workspace/editor information
architecture and every write-side contract are external through
`2026-08-24-tui-modelo-workspace-interface-adr`. Acceptance of its read-side
contract gates TUI C2; its edit implementation receipts and the operation
observation amendment gate their respective later cohorts. None is inferred
from Workspace V1.

## Rationale

The application layer is the only layer permitted to join law-selected registry
authority, secure work state, calculation materialization, readiness, closure,
and localization without reversing dependencies. An explicit inspection versus
snapshot discriminator prevents advisory schema visibility from becoming a
false authority claim. A generated field denominator makes projection coverage
explicit and fixed-point checked, while baseline-pinned facets preserve one
logical read at realistic scale without requiring eager materialization of the
entire graph.

Keeping operation observation and editing outside this record preserves their
accepted or still-missing owners. It also gives C2 a falsifiable endpoint:
complex readers can proceed once one read contract is public and proven, without
silently treating operation or editor design as complete. This is the narrow
choice supported by `2026-08-24-tui-registry-api-gate-research` and
`2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit`.

## Consequences

- Complex read-only Modelo surfaces gain one stable contract for schema,
  values, rows, lineage, readiness, closure, locale, and typed refusal.
- Static inspection remains visibly weaker than a grade-admitted snapshot; no
  downgrade can look like successful calculation or filing authority.
- Registry evolution creates a generated classification obligation for every
  new field, while backend-only grammar remains private.
- Large workspaces may be read through typed baseline-pinned facets without
  mixed registry, work, calculation, readiness, closure, or locale epochs.
- `ModeloWorkReview` remains a small bounded consumer and is neither expanded
  into Workspace V1 nor made obsolete by this decision.
- Registry incompleteness remains visible as owner-backed refused or unmeasured
  capability data; it does not destabilize the contract or become synthetic
  readiness.
- Operation observation, editing, persistence, and visual architecture remain
  blocked on their own accepted decisions and receipts.
- C2 can close as a read milestone without operation or editor implementation,
  once its external interface decision and read receipts pass. Later cohorts
  cannot cite this ADR as mutation, operation, secret-custody, or editor
  authority.
