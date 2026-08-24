---
tags:
  - '#adr'
  - '#tui-operation-observation'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:93d6c1d5fed490de119a622856058ea877ddb1aeb6fdf355ac6a43b32333aef6'
related:
  - "[[2026-08-24-tui-operation-observation-research]]"
  - "[[2026-08-11-tui-architecture-adr]]"
---

# `tui-operation-observation` adr: `public operation observation contract amendment` | (**status:** `proposed`)

## Problem Statement

The accepted `2026-08-11-tui-architecture-adr` owns operation execution,
observation, event replay, interaction, and the TUI operation projection. Its
live boundary does not yet provide the frontend-safe atomic observation needed
by the visual cohort. Allowing that cohort to consume persistence snapshots and
join replay independently would leak storage topology and create a second state
fold in the TUI.

This record is a narrow amendment to D0, D1, D3, D7, D7a, D10, and D13 of the
accepted parent. It neither supersedes that record nor establishes an
independent operation authority. The parent continues to own the supervisor,
lifecycle, journal, event stream, interaction, settlement, package topology,
and canonical plan. This amendment decides only the public observation
contract and the receipt required before its visual consumers begin. The gap
and option boundary are grounded in
`2026-08-24-tui-operation-observation-research`.

## Considerations

- Lifecycle, terminal condition, and effect remain independent accepted axes;
  a public projection must preserve all three
  (`2026-08-24-tui-operation-observation-research`).
- Current progress is derived from ordered events, while current envelope state
  is held by a revisioned snapshot; their consistency requires one observation
  anchor (`2026-08-24-tui-operation-observation-research`).
- Event replay already has cursor and resynchronization dispositions that must
  remain visible without exposing persistence records
  (`2026-08-24-tui-operation-observation-research`).
- The implemented interaction response family is review apply/reject, not the
  complete core interaction vocabulary
  (`2026-08-24-tui-operation-observation-research`).
- Public observation version, envelope revision, event cursor, registered
  payload schema, and durable journal schema answer different questions and
  cannot share a version axis
  (`2026-08-24-tui-operation-observation-research`).
- The canonical TUI architecture plan is the only implementation plan; this
  amendment may gate and revise its steps but cannot create a parallel plan.

## Considered options

- **Expose `OperationPersistedSnapshot` as the frontend contract.** Rejected:
  it publishes journal version, secure references, transition batches,
  idempotency, and interaction checkpoints as visual API.
- **Keep separate snapshot and replay calls and let each frontend join them.**
  Rejected: the calls can observe different commits and make every frontend an
  operation-state projector.
- **Persist a second frontend-complete observation record.** Rejected: it
  duplicates lifecycle truth and turns presentation evolution into durable
  schema migration.
- **Project one versioned public observation from an atomic snapshot/event read.**
  Chosen: the application owns the fold, the persistence record remains private,
  and TUI, CLI, MCP, and future frontends can consume the same anchored result.

## Constraints

- The accepted parent is stable for operation identity, lifecycle, terminal
  condition, effect, supervisor ownership, ordered events, persistence, and TUI
  topology. Its missing public observation fold is the only amended dependency.
- `cadrumo.application.operations` owns the frontend-neutral observation models,
  version dispatch, projection fold, and observation service. It imports no
  frontend or concrete adapter.
- `cadrumo.entrypoints.tui.operations` owns only controller and render view
  models over that public contract. It does not inspect journals, fold raw
  operation events, or infer capability from missing fields.
- All public models are strict, frozen, discriminated, renderer-neutral, and
  contain stable codes and safe typed facts rather than localized prose or
  untyped payload bags.
- No public observation contains a request payload or reference, idempotency
  claim, owner lease, persistence schema marker, transition-local batch,
  consumed checkpoint, response token or digest, secure operand, raw exception,
  repository identity, or adapter path.
- Public observation never grants response authority. Apply or reject requires
  a separately held secure response capability bound to the exact operation,
  interaction, revision, proposal, actor, and time.
- V1 observes only `REVIEW` interactions and the corresponding `APPLY` and
  `REJECT` responses. `INPUT` and `CHOICE`, including secret-bearing input, stay
  unavailable until their application response and custody contracts are
  separately accepted and proven.
- Event pages are bounded. Subscriber loss, an invalid or stale cursor, and
  retention resynchronization cannot settle or mutate the operation.
- The public contract is pre-release and current-only. A replacement updates
  every in-tree consumer atomically and deletes the old parser, model, projector,
  fixtures, and tests; no compatibility branch reads an older public version.
- No visual operation projection step opens until the dependency receipt
  defined here is present and validated against the live tree.

## Implementation

### Amendment to D0 and D10: public application boundary

Add a frontend-neutral observation family behind the sole public
`cadrumo.application.operations` facade:

- `OperationObservationRequestV1` carries public schema version `1`, operation
  identity, exclusive `after_cursor`, and a bounded page limit.
- `OperationObservationResultV1` is a discriminated success or typed refusal.
- `OperationPublicProjectionV1` carries the current anchored operation state.
- `OperationPublicEventPageV1` carries the bounded safe event projection and
  cursor disposition for that same anchor.

The public service accepts an unspecialized minimal version header first, then
dispatches to the exact current request model. Unsupported versions return the
stable `unsupported_operation_observation_version` refusal with requested and
supported versions as safe facts. Unknown operation, cursor-ahead, invalid
cursor, and observation-unavailable conditions likewise return typed refusals;
raw validation, repository, and persistence exceptions do not cross the facade.

Persistence-facing ports and records remain application-owned implementation
contracts for adapters. Inbound frontends may neither import nor receive
`OperationPersistedSnapshot`, `OperationJournalRecord`, raw `OperationEvent`,
`OperationPendingInteraction`, or `OperationConsumedInteraction`. The TUI
controller calls only the public observation, response, cancellation, and
detach services. Its projection module adapts public DTOs to immutable render
models without reclassifying state.

### Amendment to D1 and D3: atomic observation material

Introduce one internal observation-read port returning an application-owned
materialization from a single persistence read. That materialization binds:

- the current internal snapshot and envelope revision;
- its authoritative anchor cursor;
- the bounded history slice requested after the caller cursor;
- the fold input or checkpoint needed to derive current progress through the
  anchor; and
- replay status and restart cursor when retained history cannot continue the
  caller's fold.

The persistence adapter obtains all of those facts from one atomic journal
record read. The application projector rejects any materialization whose event
identity, revision, sequence, or cursor exceeds or disagrees with the anchor.
A later operation commit may make the returned observation stale, but cannot
make it internally inconsistent; the next request advances from its returned
cursor and revision.

The application-owned fold starts with no progress, clears progress on a phase
change, and replaces it with each progress event encountered through the anchor
cursor. A future compaction implementation must persist or derive an equivalent
fold checkpoint before emitting `expired` or `compacted`; it may not silently
drop current progress or ask the frontend to reconstruct pre-retention history.
Notices, logs, and diagnostics remain ordered page records rather than current
lifecycle fields.

### Amendment to D2 and D7: exact public state

`OperationPublicProjectionV1` contains:

- schema version, operation identity, definition identity, envelope revision,
  and anchor cursor;
- lifecycle, nullable terminal condition, effect, phase code, start time, and
  update time;
- nullable current progress with completed, total, unit code, phase code, event
  sequence, and envelope revision;
- declared close policy, cancellation capability and current availability,
  cancellation-request and acknowledgement state, and execution and cleanup
  deadline state;
- a discriminated pending-interaction projection;
- terminal result or refusal reference only when settlement provides it; and
- redacted diagnostic reference only, never diagnostic prose.

Lifecycle, terminal condition, and effect preserve the accepted enums and
validation relationship. Spinner, terminal copy, enabled controls, countdown,
and colors are TUI derivations and do not enter the public model. Capability and
current availability remain separate: a cooperatively cancellable definition
does not imply `cancellable_now` inside an irreversible section.

`OperationPublicEventPageV1` echoes the observation anchor, requested cursor,
status, ordered safe event records, next cursor, and nullable restart cursor.
Statuses preserve `page`, `caught_up`, `expired`, and `compacted`; unknown
operation is a result refusal. A `page` is contiguous and ends at `next_cursor`.
`expired` or `compacted` returns no event rows, advances to an authoritative
restart cursor, and instructs the consumer to replace event-derived local state
with the accompanying projection before continuing. No row may exceed the
projection's anchor cursor.

### Amendment to D4 and D7a: bounded interaction observation

The pending-interaction projection is discriminated as `none`,
`review_available`, or `unsupported`. `review_available` carries only safe
operation and interaction identities, operation revision, presentation and
response-schema codes, expiry, and a safe domain review-projection reference.
It never carries the response token or digest, reviewed secure operand,
continuation digest, baseline digest, proposed-effect digest, or consumed
checkpoint.

The public projection separately states whether the composed caller currently
has an exact secure response capability. Apply and reject are enabled only when
that capability is present and the projected interaction is still current.
Observation after detach or from a fresh process remains available without it,
but response controls are disabled; observation cannot recreate bearer
authority. `INPUT` or `CHOICE` produces the `unsupported` interaction
disposition with a stable code while lifecycle, phase, progress, cancellation,
and settlement remain visible. Expanding that scope requires a later amendment
and the existing `EphemeralSecretSubmission` gate where secret input is involved.

### Public version separation and refusal

Public observation version `1` is independent of:

- envelope revision, which orders lifecycle compare-and-swap state;
- event cursor, which orders replay;
- operation-definition and registered request/result schema identity; and
- durable journal schema version, which is private to persistence hydration.

None may be substituted for another or copied into a shared `version` field.
The public minimal-header dispatcher supports exactly the current observation
version. Pre-release breaking change replaces V1 in one cutover; durable-schema
evolution follows its own compatibility regime and can neither broaden nor
silently downgrade the public observation version.

### Conformance and dependency receipt

The canonical `tui-architecture` plan is amended before `W05.P11.S60` to
produce the machine-readable receipt at
`.vault/reference/2026-08-24-tui-operation-observation-dependency-receipt.md`.
A production conformance test validates that receipt against the live tree.
It opens only the C0 operation-platform visual-projection cohort; it cannot
claim readiness for the C1 read-only Modelo relocation, C2 workspace, C3 edit,
C4 action-enrollment, or C5 fixed-point cohorts. The receipt gate records and
mechanically verifies:

- receipt schema version, the accepted parent and this approved amendment,
  their approval status, and commit ancestry;
- public observation version and deterministic schema fingerprint;
- the exact public export and observation/cancel/detach/respond capability
  inventories and their digests, plus absence of persistence DTO imports from
  TUI, CLI, and MCP consumers;
- real-adapter atomic observation under an interleaved transition;
- independent lifecycle, terminal-condition, and effect parity;
- progress fold and phase-reset parity through the anchor cursor;
- bounded page, caught-up, cursor-ahead, expired, compacted, detach, reconnect,
  and resynchronization behavior;
- review-only interaction projection, stale response refusal, response-control
  disablement without secure capability, and input/choice refusal;
- strict public serialization roundtrips and unsupported-version refusal; and
- secret, request, checkpoint, persistence, exception, and diagnostic-prose
  non-retention.

`W05.P11.S60` then consumes the public service rather than supervisor
`inspect`/persistence DTOs; `S61` projects only
`OperationPublicProjectionV1`; `S62` consumes
`OperationPublicEventPageV1`; and `S63` is narrowed to review/apply/reject until
a later accepted interaction expansion. `S64` through `S67` retain their
accepted visual and behavior ownership over those contracts. The later
`tui-interface` dependency receipt includes the approved observation version
and the successful live-tree gate. No separate implementation plan is created.

## Rationale

Only the application layer can observe authoritative envelope state and ordered
events without exposing persistence or making a frontend reconstruct lifecycle
truth. One atomic materialization closes the snapshot/replay race while keeping
the accepted supervisor, journal, and event stream as the sole authorities.
The public projection preserves the three accepted state axes and gives every
frontend one current-only version boundary. Narrowing V1 interaction to proven
review apply/reject behavior prevents an enum declaration or retained token
digest from masquerading as an implementable secure interaction. These are the
decisive ownership, consistency, and honesty criteria identified by
`2026-08-24-tui-operation-observation-research`.

## Consequences

- TUI operation work gains one frontend-safe atomic observation target without
  learning journal V3 or secure checkpoint topology.
- Progress, cursor replay, detach, reconnect, and resynchronization share one
  anchor and cannot be stitched from conflicting revisions.
- Terminal condition remains visible independently from lifecycle, effect,
  result, refusal, and localized terminal copy.
- CLI, MCP, and future frontends may reuse the public contract, while retaining
  their own presentation and waiting strategies.
- Persistence adapters need one atomic observation-read capability and the
  application needs a deterministic event fold and public version dispatcher.
- Review state remains observable after detach, but a new observer cannot apply
  or reject without separately recovered secure response authority.
- Input and choice interaction rendering remains blocked rather than falsely
  advertised by the initial modal.
- The canonical plan must be amended and its dependency receipt must pass before
  visual operation projection begins; this record creates no parallel plan.
- Public-contract changes and durable journal changes can proceed independently,
  but each retains its own strict current-version cutover and conformance burden.
