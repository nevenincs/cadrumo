---
tags:
  - '#adr'
  - '#tui-registry-api-gate'
date: '2026-08-24'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:58788a2b90079a2190525c60b3854074cfdd30eb1f9dfdffc14bfadd795b6d0b'
related:
  - '[[2026-08-24-tui-registry-api-gate-research]]'
  - '[[2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit]]'
  - '[[2026-08-11-tui-architecture-adr]]'
  - '[[2026-08-11-tui-interface-adr]]'
  - '[[2026-08-10-casilla-schema-read-model-adr]]'
  - '[[2026-08-10-casilla-schema-canonical-derivations-adr]]'
  - '[[2026-08-10-casilla-schema-blocker-spine-adr]]'
  - '[[2026-08-08-profile-requirement-grounding-adr]]'
  - '[[2026-06-04-modelo-addressing-ux-adr]]'
  - '[[2026-06-10-period-revision-resolution-adr]]'
  - '[[2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr]]'
  - '[[2026-08-24-registry-completeness-closure-adr]]'
  - '[[2026-08-22-source-casilla-integration-adr]]'
  - '[[2026-08-04-modelo-localization-cascade-adr]]'
  - '[[2026-08-09-cli-action-envelope-hardening-adr]]'
  - '[[2026-08-24-tui-modelo-workspace-interface-adr]]'
  - '[[2026-08-25-tui-architecture-workspace-owner-seam-reconciliation-audit]]'
---

# `tui-registry-api-gate` adr: `read-only Modelo workspace projection and capability facade` | (**status:** `accepted`)

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
- `ModeloWorkReview` remains the accepted canonical bounded C1 projection with
  one public producer. Workspace V1 is a wider read model around that exact
  facet, not a second assembler or its replacement
  (`2026-08-10-casilla-schema-read-model-adr`).
- Profile readiness retains an explicit per-operation assessment axis whose
  `false` state means nothing on that axis was examined and whose `true` state
  still means only that tokenised required fields were examined. Neither state
  is a Modelo-completeness verdict
  (`2026-08-08-profile-requirement-grounding-adr`).
- Public operation observation is the external amendment established by
  `2026-08-24-tui-operation-observation-adr`. Modelo workspace presentation and
  editing are the external interface/write-side boundary established by the
  accepted `2026-08-24-tui-modelo-workspace-interface-adr`. Neither record is
  implemented merely because Workspace V1 exists.

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
- Every canonical owner contributing to a successful projection exposes through
  its public facade one native atomic projection-plus-generation capture and one
  current-generation read. The application-owned Workspace boundary alone wraps
  that surface in S126 contract, stamp, epoch, and port types. A lower layer never
  imports or returns a `ModeloWorkspace*` type. An owner that cannot provide the
  native atomic pair cannot participate in a successful Workspace projection.
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

### Canonical bounded review facet

`ModeloWorkspaceProjection.work_review` is the canonical bounded C1 facet. When
the admission path permits a work review it is the exact frozen
`ModeloWorkReview` produced for the resolved coordinate by
`build_modelo_work_review(...)`; static inspection and other ineligible paths
carry a typed facet disposition rather than a partial or reconstructed review.
The Workspace producer must not independently join or reinterpret the Casilla
schema, realised values, verification, findings, progress, blockers, or origin
layers owned by that record.

If atomic Workspace capture requires sharing a lower-level materialization,
`build_modelo_work_review(...)` and the Workspace producer delegate to one
application-owned pure semantic assembler over the same captured inputs. The
accepted function remains the sole public `ModeloWorkReview` producer. A
fixed-point test compares the complete Workspace facet with the complete public
producer result, including absent-work and refusal behavior, for every selected
fixture coordinate. Any unequal field, identity, ordering, disposition, or
evidence reference fails C1 parity and therefore C2; a second independently
maintained review join is forbidden.

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
`ProjectionModeloReadiness` without collapsing its axes. The Workspace DTO
preserves `profile_ready`, `per_operation_requirements_assessed`,
`registry_ready`, `binding_ready`, `ledger_preflight_required`, nullable
`ledger_ready`, the corresponding missing requirements/issues/refusals, and
the aggregate `ready` value exactly as produced. It does not rename or erase an
unassessed axis. In particular, `ProjectionModeloReadiness.ready` alone can
never produce capability disposition `available`: the aggregate currently
does not prove that the per-operation profile axis was assessed, and
`per_operation_requirements_assessed = true` proves only the tokenised subset,
not complete Modelo requirements. `available` requires a separately stamped,
explicit verdict from the canonical producer responsible for that exact
capability and coordinate. Without that verdict, or when its declared
assessment is incomplete or unknown, the capability is `unmeasured` rather
than inferred.

Registry completeness is selected from the canonical cross-authority closure
report and its temporal, source-connectivity, and filing-export limbs. Blockers
retain their native code and total `OperatorActionAxis` projection. An optional
recovery `ActionReference` is copied from the action catalogue; it is guidance
only and grants no invocation authority. If a canonical production producer or
join has not landed, the workspace reports `unmeasured` and never recreates a
development-only join.

A domain refusal contains a stable code, affected capability or admission
boundary, requested coordinate, selected coordinate when resolution reached
one, safe typed facts, canonical evidence references, responsible
owner/disposition, reconsideration condition, and optional canonical action
reference. The pre-parse version refusal remains the minimal version-only arm.
Localized command prose and raw exceptions never enter either arm. Global
registry completeness need not be satisfied for Workspace V1 to render; an
evidence-backed refusal is valid workspace data.

### Native-owner capture and application-owned Workspace contract seam

The semantic projection and its consistency generation remain owned by each
canonical contributor. Each owner exposes through its canonical public facade
one native operation that atomically returns an immutable or snapshot-isolated
owner projection together with an owner-local ABA-safe monotonic generation,
plus one native read of the current generation. The generation advances on
every owner-state transition that can change the contributed projection,
including A -> B -> A. It is not a payload digest, timestamp, value-equality
marker, Workspace baseline, or counter minted by Workspace code.

Native generations are monotonic within one owner process incarnation. An
opaque Workspace baseline and every cursor bind the application process
incarnation as part of their token derivation, and a follow-up presented to a
different incarnation refuses as `workspace_changed`; it never compares a
restarted integer generation as though it belonged to the earlier process.
The incarnation coordinate grants no authorization, contains no owner data,
and is not a substitute owner generation or a durable shadow counter.

The Workspace-specific contract remains owned exclusively by
`cadrumo.application.modelo`. For each contributor kind, the application
declares exactly one `ModeloWorkspaceProducerContractV1` and exactly one
`ModeloWorkspaceAtomicProjectionPortV1` realization over the owner's public
native capture surface. That realization performs exactly one native capture,
derives the safe Workspace contribution only from the captured immutable or
otherwise snapshot-isolated value,
constructs `ModeloWorkspaceProducerStampV1` from the application contract, and
preserves the owner's generation unchanged in `ModeloWorkspaceEpochV1`.
`read_current_stamp_and_epoch` combines the same contract-derived stamp with
the canonical owner's native current-generation read. A lower layer never
imports, constructs, or returns a `ModeloWorkspace*` type.

This registration is application composition, not a second semantic owner,
compatibility adapter, or bridge. It owns no contributor state, cache,
generation, selector, review or readiness calculation, closure join, source
graph, or locale resolution; it cannot reread a repository, loader, or owner
while projecting a captured value. No shim, fallback, non-`__init__` re-export
bridge, adapter-package implementation, or alternate owner API is permitted.
Promotion through the canonical owner's package facade remains mandatory. If
an owner cannot provide atomic native capture and current-generation semantics,
that contributor cannot be registered and Workspace returns
`consistency_unavailable`.

The contributor fixed point is exact:

| Kind | Canonical semantic owner | Producer identity |
|---|---|---|
| `registry` | `domain.calculations.registry` | `validated_registry_projection` |
| `work` | `application.modelo.work_addressing` | `resolved_work_target` |
| `bounded_review` | `application.modelo.work_review` | `modelo_work_review` |
| `calculation` | `application.modelo.calculation` | `calculation_materialization` |
| `readiness` | `application.state_projection` | `modelo_readiness` |
| `closure` | `application.registry` | `registry_closure` |
| `locale_catalogue` | `locales` | `locale_catalogue` |
| `field_manifest` | `application.modelo.workspace_manifest` | `workspace_field_manifest` |

`ModeloWorkspaceProducerContractInventoryV1` inventories these eight
application-owned S126 registrations, not contracts implemented by lower-layer
owners. Each contract fingerprints the safe application projection schema.
One S126 capture calls its canonical owner's native capture exactly once,
projects only that captured value, and returns the application projection,
contract-derived stamp, and unchanged native generation. The second-pass read
returns the unchanged contract-derived stamp and the same owner's current
native generation. Neither operation may mint an owner generation or obtain a
second semantic value. Missing, duplicate, stale, misidentified, or
unclassified registrations fail the generated fixed-point gate.

### Locale and consistency boundary

Each localized field carries its canonical key plus requested language,
resolved language, and exact resolution disposition. Required Spanish absence
refuses; a non-Spanish miss may use only the canonical Spanish fallback. The
same semantic record has identical identities, values, provenance, and
capabilities in every locale.

`ModeloWorkspaceProjection` is one logical point-in-time read, and the
application owns its complete semantic join. Static inspection captures exactly
`registry`, `work`, `locale_catalogue`, and `field_manifest`; it does not read
bounded review, calculation, readiness, or closure state. Graded snapshot
captures all eight registered contributors. Assembly follows this exact
protocol for the selected admission set:

1. invoke each application-owned S126 registration, whose single call captures
   the canonical owner's native projection and generation atomically and wraps
   them without another owner read;
2. assemble only from those captured projections, with no live owner re-read
   hidden inside the join;
3. ask each same registration for its current coordinates; it combines the
   unchanged S126 contract stamp with the canonical owner's native
   current-generation read, and both coordinates must equal the capture; and
4. only after every comparison succeeds, mint one safe opaque
   `ModeloWorkspaceBaseline` over the sorted contributor tuple, resolved
   request coordinate, selected revision, Workspace contract version,
   registry schema identity and fingerprint, locale-catalogue stamp, and
   field-manifest digest.

An unknown or changed epoch or producer stamp causes a bounded whole-assembly
retry and then a typed `workspace_changed` or `consistency_unavailable`
refusal. No baseline is minted before validation, and A -> B -> A invalidates
the capture. Every collection without an authoritative finite bound is
delivered through a typed bounded facet, page, or expansion. Those delivery
shapes carry and revalidate the same sorted contributor tuple, contract
version, schema identity and fingerprint, selected revision, and baseline.
Unpinned pagination and a contributor that cannot atomically return projection
plus ABA-safe epoch are forbidden. The token contains no raw value, secret,
source identity, or reusable authorization.

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
complete `ModeloWorkReview` facet fixed-point parity with its sole public
producer; full-versus-faceted baseline consistency; stale and mid-read refusal;
producer-contract/stamp drift; torn-read refusal; and ABA A -> B -> A
invalidation. Readiness fixtures include aggregate `ready = true` with
`per_operation_requirements_assessed = false`, assessed-but-token-partial
requirements, and mixed profile/registry/binding/ledger axes. They prove exact
axis parity and prove that no case becomes `available` from `ready` or
assessment alone without the separately stamped canonical capability verdict.
The suite also covers version refusal, forbidden imports, sensitive-data
non-retention, and the live C2 dependency-receipt validator.

Conformance also proves a one-to-one fixed point between the eight S126
registrations and the eight canonical native owner surfaces; exact contributor
identities and admission-specific capture sets; exactly one native capture per
S126 capture; immutable or snapshot-isolated captured values; unchanged owner
generations; cross-incarnation baseline and cursor refusal; and absence of any
application-minted, persisted, reset, or substituted owner generation. Domain,
locale, and other lower-layer modules importing or returning a
`ModeloWorkspace*` type fail the boundary gate.

### C2 complex-read gate and external prerequisites

Existing bounded `ModeloWorkReview` and backend campaigns may continue. The C2
complex-read cohort remains blocked until all of these receipts exist:

1. this ADR is accepted and Workspace V1 is exported from the public
   application facade;
2. for a TUI consumer, `2026-08-24-tui-modelo-workspace-interface-adr` is
   accepted and its `ModeloWorkspaceC1ExitReceiptV1` at
   `.vault/reference/2026-08-24-tui-modelo-workspace-interface-c1-exit-receipt.md`
   is green; that record retains ownership of destinations, view models,
   bounded rendering, and visual conformance;
3. the authority-grade decision is accepted or formally reconciled and both
   admission paths use its public contracts;
4. canonical readiness and closure producers are public and their Workspace
   parity tests are green, although individual revisions may still carry
   evidence-backed refusals;
5. the generated current-HEAD field-classification manifest has zero
   unclassified paths and its digest is recorded;
6. every canonical owner publishes its native atomic capture surface, every
   application registration publishes a current stamped producer contract, and
   the native-surface/S126 one-to-one fixed point is green;
7. the complete V1 conformance suite above is green; and
8. the machine-readable
   `.vault/reference/2026-08-24-tui-registry-api-gate-c2-dependency-receipt.md`
   validates as `ModeloWorkspaceC2DependencyReceiptV1` under
   `validate_modelo_workspace_c2_dependency_receipt` on current HEAD.

`ModeloWorkspaceC2DependencyReceiptV1.predecessors` is the closed, ordered
`ModeloWorkspaceC2PredecessorTupleV1`:

1. this accepted ADR's stem, accepted commit, and body hash;
2. the accepted `2026-08-24-tui-modelo-workspace-interface-adr` stem, accepted
   commit, and body hash;
3. the `ModeloWorkspaceC1ExitReceiptV1` path above, producing commit, and
   artifact digest;
4. the accepted or formally reconciled authority-grade decision stem,
   disposition, commit, body hash, and reconciliation-artifact digest when
   reconciliation was required; and
5. the native-owner surface inventory and seam-conformance digest plus the
   `ModeloWorkspaceProducerContractInventoryV1` schema version, producing
   commit, and artifact digest.

The C2 receipt additionally records the sorted native-owner surfaces, producer
contracts and stamps, captured epoch tuple/digest, process-incarnation refusal
proof, Workspace version and schema fingerprint, generated field-manifest
digest, baseline and locale proofs, source ancestry, and exact complex-read
routes opened. Its validator rejects an absent or reordered
predecessor, a proposed/unapproved decision, a non-ancestor producing commit,
artifact or body-hash drift, missing or mismatched producer stamps, epoch-
protocol drift, a non-green C1 receipt, or a route outside C2. Mocks, prose
attestations, and a receipt produced from a different tree cannot open the gate.

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
- `ModeloWorkReview` remains the canonical bounded C1 record and appears
  unchanged as the Workspace review facet; Workspace V1 neither expands it nor
  duplicates its semantic join.
- Registry incompleteness remains visible as owner-backed refused or unmeasured
  capability data; it does not destabilize the contract or become synthetic
  readiness.
- Operation observation, editing, persistence, and visual architecture remain
  blocked on their own accepted decisions and receipts.
- C2 can close as a read milestone without operation or editor implementation,
  once its external interface decision and read receipts pass. Later cohorts
  cannot cite this ADR as mutation, operation, secret-custody, or editor
  authority.
