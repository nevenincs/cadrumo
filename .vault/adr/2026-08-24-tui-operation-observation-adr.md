---
tags:
  - '#adr'
  - '#tui-operation-observation'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e8f44be175c879eed50517f3590a50885714f8152b9d69892c9c97e05a29ac9a'
related:
  - '[[2026-08-24-tui-operation-observation-research]]'
  - '[[2026-08-11-tui-architecture-adr]]'
  - '[[2026-08-24-tui-registry-api-gate-adr]]'
  - '[[2026-08-24-tui-modelo-workspace-interface-adr]]'
  - '[[2026-08-24-modelo-edit-contract-adr]]'
  - '[[2026-07-09-compatibility-lifecycle-adr]]'
  - '[[2026-08-10-current-schema-only-purge-adr]]'
---

# `tui-operation-observation` adr: `public operation contract parent-amendment staging` | (**status:** `rejected`)

## Problem Statement

The accepted `2026-08-11-tui-architecture-adr` owns operation execution,
observation, event replay, interaction, secure operand handling, effect
reconciliation, and the TUI operation projection. Its live boundary does not
yet provide the frontend-safe atomic observation needed by the visual cohort.
It also lacks a registered public resolver for safe REVIEW content, a typed
single-consumer custody contract for transient financial edit operands, a
typed operation-result-to-Workspace-refresh adapter, and stable public schema
identities spanning those contracts. Leaving those seams to TUI or Workspace
would leak secure and persistence topology and create competing authorities.

This record is an approval staging record, not an independent decision owner.
Its proposed clauses amend D0, D1, D2, D3, D4, D5, D6, D7, D7a, D10, and D13
of the accepted parent only after they are copied into that parent in place.
This staging ADR must never become `accepted`: during review it remains
`proposed`; after the parent amendment lands it is retained as `rejected`, where
rejection means that a sibling authority was rejected, not that the incorporated
clauses were declined. There is therefore never a state with two accepted
owners. The parent continues to own the supervisor, lifecycle, journal, event
stream, interaction, settlement, package topology, and canonical plan. The gap
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
- A REVIEW checkpoint has secure operand authority but no registered safe
  public projector; observation and response bearer authority must stay
  separate (`2026-08-24-tui-operation-observation-research`).
- The generic ephemeral-secret broker and persistent secure-operand store do
  not supply the typed baseline-bound handoff and crash semantics required by a
  financial editor (`2026-08-24-tui-operation-observation-research`).
- A generic terminal `result_ref` cannot be interpreted as a Workspace target
  by a frontend; the operation definition must register the domain adapter
  (`2026-08-24-tui-operation-observation-research`).
- Python request/result classes are not public schema identities; a safe
  definition manifest and digest must bind every public projection seam
  (`2026-08-24-tui-operation-observation-research`).
- The repo remains `PRE_RELEASE`: private request, interaction, and journal
  schemas accept only the current shape, and the accepted parent's contrary
  migration sentence must be replaced during adoption
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
- **Accept this staging ADR as a sibling operation authority.** Rejected: it
  would duplicate the accepted parent's ownership of observation, interaction,
  custody, settlement, and the canonical plan.
- **Let TUI or Workspace resolve REVIEW/result references and retain the edit
  operand.** Rejected: it publishes secure-reference meaning, makes frontend
  teardown part of reconciliation, and gives Workspace operation authority.
- **Reuse `EphemeralSecretSubmission` or persist every editor operand in the
  secure-reference store.** Rejected: the former has no typed edit-baseline or
  durable handoff protocol; the latter retains a second pre-effect draft copy.
- **Amend the accepted parent in place with one registered public contract set,
  a distinct transient-financial-operand policy, and split C0/C3 receipts.**
  Chosen: authority remains singular and each dependency is proven only when it
  exists.

## Constraints

- This record has no implementation authority while `proposed`. Adoption is an
  in-place edit of the accepted parent followed in the same architecture change
  by retaining this record as `rejected`; it is never marked `accepted` and
  never supersedes the parent.
- The accepted parent is stable for operation identity, lifecycle, terminal
  condition, effect, supervisor ownership, ordered events, persistence, secure
  reviewed operands, and TUI topology. The clauses staged here refine its
  public projection and add missing registered seams without moving ownership.
- `cadrumo.application.operations` owns the frontend-neutral observation,
  REVIEW-resolution, transient-financial-operand custody, and
  result-to-refresh protocols, their version dispatch, projection fold, and
  services. It imports no frontend, Modelo implementation, Workspace producer,
  or concrete adapter.
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
- Public schema identities contain stable IDs, explicit versions, and canonical
  schema fingerprints only. They never contain Python module/class names,
  persistence discriminators, callable identities, or raw JSON schema.
- Public observation never grants response authority. Apply or reject requires
  a separately held secure response capability bound to the exact operation,
  interaction, revision, proposal, actor, and time.
- V1 observes only `REVIEW` interactions and the corresponding `APPLY` and
  `REJECT` responses. `INPUT` and `CHOICE`, including secret-bearing input, stay
  unavailable until their application response and custody contracts are
  separately accepted and proven.
- A safe REVIEW projection is read-only and never conveys a response bearer,
  reviewed-operand reference or digest, continuation digest, baseline digest,
  proposed-effect digest, or financial value.
- `transient` describes operand custody, not `OperationDurability.EPHEMERAL`.
  An effectful financial edit remains a `RECORDED` operation with interrupt
  reconciliation and an authoritative domain effect receipt.
- Financial operands may exist transiently in application memory and, after a
  successful governed effect, in canonical encrypted secure storage. They never
  enter journals, events, receipts, projections, diagnostics, traces, temporary
  files, caches, content digests, or frontend-retained operation state.
- Event pages are bounded. Subscriber loss, an invalid or stale cursor, and
  retention resynchronization cannot settle or mutate the operation.
- The public contract is pre-release and current-only. A replacement updates
  every in-tree consumer atomically and deletes the old parser, model, projector,
  fixtures, and tests; no compatibility branch reads an older public version.
- Private operation persistence is also current-only while the repo-committed
  compatibility regime is `PRE_RELEASE`. A cutover requires zero affected
  nonterminal invocations, refuses every non-current private shape, and deletes
  the superseded readers, migrators, fixtures, and tests. This record cannot authorize a
  post-release upgrader; only the compatibility-checkpoint authority can change
  that regime.
- No visual operation projection step opens until the dependency receipt
  defined here is present and validated against the live tree.

## Implementation

### Adoption procedure and authority invariant

Reviewers approve or reject this staged amendment without changing this
record's status to `accepted`. Approval authorizes one architecture change with
this order and invariant:

1. replace the accepted parent's D5 sentence “Recorded schemas are versioned
   and migrated before acquisition” with the PRE_RELEASE contract: recorded
   private schemas carry an explicit current marker; acquisition refuses every
   non-current shape; a breaking cutover requires zero affected nonterminal
   invocations and deletes the old readers, migrators, fixtures, and tests; and
   future post-release upgrade behavior remains owned exclusively by the
   compatibility-checkpoint authority;
2. copy the approved clauses into the existing
   `2026-08-11-tui-architecture-adr` under its D0 through D7a, D10, and D13
   ownership; preserve that record's stem and `accepted` status;
3. link the parent to this research and staging record as provenance, without a
   supersession edge;
4. change this staging record from `proposed` to `rejected` and state that its
   separate authority was rejected because the clauses now live in the parent;
5. regenerate both affected feature indexes and run ADR-status, schema, link,
   and feature checks; and
6. amend the one canonical `tui-architecture` plan only after the parent body
   hash and rejected staging state are final.

No commit may mark this staging ADR `accepted`, and no receipt may cite it as
governing authority. The C0 and future operand receipts cite the accepted
parent's post-amendment body hash and use this rejected record only as adoption
provenance. If the parent amendment is not applied, this record remains
`proposed` and no implementation cohort opens.

### Amendment to D6: registered public definition and schema manifest

The canonical operation registry gains `OperationSchemaIdentityV1` and
`OperationPublicDefinitionContractV1`. `OperationSchemaIdentityV1` contains one
stable schema ID, positive schema version, and SHA-256 fingerprint of the
canonical closed JSON schema. `OperationPublicDefinitionContractV1` contains:

- manifest version `1`, `OperationDefinitionId`, and nullable canonical
  `ActionReference`;
- request and nullable result schema identities;
- nullable safe REVIEW-projection and interaction-response schema identities;
- nullable Workspace-refresh-target schema identity;
- the declared interaction, request-storage, transient-financial-operand,
  durability, cancellation, deadline, reconciliation, effect, and permitted
  frontend facts that are safe to project; and
- `definition_contract_digest`, computed over the canonical ordered value of
  those fields, excluding the digest itself.

The registry binds each schema identity to its exact strict Pydantic model and
validates the fingerprint produced by `model_json_schema()` at construction.
It rejects duplicate IDs, duplicate `(schema ID, version)` pairs with different
fingerprints, missing declared models, undeclared projectors/adapters, and any
manifest whose digest does not reproduce. Registry composition may bind a
domain-owned model, projector, or adapter through public protocols, but
`application.operations` never statically imports that domain package. Python
module, class, callable, and adapter-path names are not manifest fields.

`OperationPublicContractSetV1` is the canonical sorted inventory of every
public operation definition contract and has its own deterministic
`contract_set_digest`. The inventory, each definition digest, and every schema
fingerprint are fixed-point checked against live registry composition. A
registered public request, result, review, response, or refresh schema changes
only by current-version replacement of the corresponding identity and a new
definition and contract-set digest; it cannot drift behind an unchanged ID.

Submission copies the selected `definition_contract_digest` into the durable
invocation identity checkpoint in the same atomic transition as the request
reference and initial lifecycle event. It does not persist the public DTO or
raw schema. Resume, observation, REVIEW resolution, response, refresh-target
resolution, and reconciliation all require the current registry definition to
reproduce that digest. A breaking definition or private-schema cutover must
first prove there are zero affected nonterminal invocations. It then deletes
the superseded private request, interaction, and journal readers, migrators,
fixtures, and tests; acquisition refuses every non-current shape. It may not
translate a stored invocation or rewrite only its digest. A current-shape
invocation whose definition digest no longer matches refuses acquisition and
enters normal reconciliation; a non-current private shape fails at hydration
and is never interpreted or reconciled as current.

### Amendment to D0 and D10: public application boundary

Add a frontend-neutral observation family behind the sole public
`cadrumo.application.operations` facade:

- `OperationObservationRequestV1` carries public schema version `1`, operation
  identity, exclusive `after_cursor`, and a bounded page limit.
- `OperationObservationResultV1` is a discriminated success or typed refusal.
- `OperationPublicProjectionV1` carries the current anchored operation state.
- `OperationPublicEventPageV1` carries the bounded safe event projection and
  cursor disposition for that same anchor.

The same facade exports the independently versioned
`OperationReviewProjectionRequestV1`/`OperationReviewProjectionResultV1` and
`OperationWorkspaceRefreshTargetRequestV1`/
`OperationWorkspaceRefreshTargetResultV1` families defined below. Registered
success variants are generically specialized by their exact declared Pydantic
model; there is no `dict[str, Any]`, arbitrary JSON, or frontend callback
escape hatch. Refusal variants remain closed and renderer-neutral.

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
controller calls only public observation, review-projection, response,
cancellation, detach, and refresh-target services exposed to it by application
composition. Its projection module adapts public DTOs to immutable render
models without reclassifying state. Entry points never call the
financial-operand custody port directly; a domain edit application service
performs that handoff inside one application-owned submission flow.

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

- observation schema version, operation identity, definition identity,
  nullable canonical action reference, envelope revision, and anchor cursor;
- the exact `OperationPublicDefinitionContractV1`, including request, nullable
  result, nullable REVIEW-projection, nullable interaction-response, and
  nullable Workspace-refresh-target schema identities, plus its
  `definition_contract_digest` and the containing `contract_set_digest`;
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

The schema identities and digests are public compatibility facts, not payload
or response authority. A projection is refused if its operation definition is
absent from the current contract set, if a recorded definition digest cannot be
validated against the invocation's enrolled definition, or if its registered
schema identities disagree with the projector selected for that operation.

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

The caller-independent public projection states only that the registered
definition supports the response family and whether the pending interaction is
current. Possession of response authority is composed separately through the
existing secure response service, which validates a runtime-only bearer against
the projected operation, interaction, revision, proposal, actor, and expiry and
returns a safe availability result for that exact revision. The bearer is not a
field of any observation or review DTO. Apply and reject are enabled only when
that separate result is available and the projected interaction remains
current. Observation after detach or from a fresh process remains available
without it, but response controls are disabled; observation cannot recreate
bearer authority. `INPUT` or `CHOICE` produces the `unsupported` interaction
disposition with a stable code while lifecycle, phase, progress, cancellation,
and settlement remain visible. Expanding that scope requires a later amendment
and the existing `EphemeralSecretSubmission` gate where secret input is involved.

#### Registered safe REVIEW projection resolver

`review_available` carries an `OperationReviewProjectionReferenceV1` made only
from operation ID, interaction ID, operation revision, REVIEW-projection schema
identity, definition-contract digest, and expiry. It contains no persistence or
secure-operand reference. A caller passes that reference under minimal header
`review_projection_version = 1` to `OperationReviewProjectionRequestV1`.
`OperationReviewProjectionResultV1` is a closed success/refusal union. The
success contains the exact registered
`OperationReviewProjectionSuccessV1[ReviewProjectionT]`, specialized by the
definition's safe review model and echoing its schema identity and definition
digest.

For every definition declaring `REVIEW`, the registry must bind exactly one
strict safe review type, `OperationSchemaIdentityV1`, and side-effect-free
projector from the internally resolved reviewed operand and current interaction
facts to that type. Construction rejects REVIEW without that triple. The
operation-owned resolver reloads the authoritative operation and pending
checkpoint, validates operation/interaction/revision/expiry/definition digest
and schema identity, resolves the encrypted reviewed operand only behind the
secure application port, validates its registered private type, invokes the
projector, validates the exact public type and fingerprint, and then drops its
local operand reference. The projector may emit explanatory safe facts but may
not emit financial values, secure references, any operand/content digest,
continuation or response material, repository identity, or localized prose.

The refusal codes are exactly
`unsupported_review_projection_version`, `unknown_operation`,
`review_not_pending`, `stale_review_reference`, `review_expired`,
`definition_contract_mismatch`, `review_schema_mismatch`, and
`review_projection_unavailable`. Raw validation, decryption, repository, and
projector errors collapse to the last safe refusal and redacted diagnostic
reference. Resolution is read-only: it neither consumes the checkpoint nor
changes expiry, lifecycle, revision, or response capability. APPLY/REJECT still
requires the separate exact secure response bearer and current revision.

### Amendment to D3a, D4, D5, and D6: transient financial operand custody

Add the current-only `OperationTransientFinancialOperandProtocolV1`, explicitly
distinct from `OperationDurability.EPHEMERAL`, `EphemeralSecretSubmission`, and
the persistent `OperationSecureOperandLookup`. A definition opting in binds one
`OperationTransientFinancialOperandDeclarationV1`: exact typed operand model and
schema identity, maximum lifetime, exact edit-baseline schema identity,
reconciliation policy `INTERRUPT`, and an authoritative domain effect-receipt
resolver. Registry
construction permits it only for `RECORDED` operations that declare effect
`NONE`, `UNKNOWN`, and every domain effect the writer can prove.

A domain edit application service submits an already validated typed operand
through `OperationTransientFinancialOperandSubmissionV1`; no entrypoint receives
or retains the operation custody grant. The service first creates or resolves
the exact credential-free operation and receives a runtime-only 256-bit
submission grant from the supervisor. The grant is passed within that same
application call, is never serialized or returned to TUI, and is discarded
after success or refusal. The durable
`OperationTransientFinancialOperandRequirementV1` contains only operation and
definition identity, invocation revision, random-grant fingerprint, operand
schema identity, the declaration's edit-baseline schema identity, a safe opaque
domain edit-baseline reference, and expiry. The fingerprint is over fresh
high-entropy randomness and never over operand content. For Modelo the reference
identifies `ModeloEditBaselineV1`; the Workspace read baseline is never accepted
as a substitute.

The supervisor owns one in-memory entry per exact requirement and serializes
submission, consumption, cancellation, expiry, and settlement under the same
operation transition lock. It validates the concrete registered operand type
without serializing or hashing its values, takes its sole strong custody
reference, and atomically advances the durable custody checkpoint from
`awaiting_submission` to `bound`. Mismatch, stale revision, wrong definition or
schema, expired grant, duplicate submission, duplicate consumption, and an
already terminal operation are typed refusals. The submitting application
scope drops its operand and grant references after transfer.

Only the registered executor receives
`OperationTransientFinancialOperandAccessV1`. One consume attempt advances the
durable checkpoint `bound -> delivery_started` before the broker removes its
entry, then `delivery_started -> delivery_acknowledged` as the executor accepts
the guarded value. No second consumer can observe it. Exiting the guarded scope
drops all supervisor and executor custody references and advances to
`released`; `released` proves release only, not an effect. The implementation
zeroises mutable backing buffers where the declared model provides them and
drops every other strong reference promptly; it must not claim that immutable
Python object memory can be reliably erased.

Expiry before `delivery_started` discards the runtime entry and settles
`INTERRUPTED/NONE`; it is a submission bound, not an aggregate execution
deadline. A pre-delivery cancellation discards the entry and, after supervisor
acknowledgement and cleanup, settles `CANCELLED/NONE`. Once `delivery_started`
is durable, expiry cannot revoke executor access and
cancellation cannot claim a terminal outcome until the executor or
reconciliation settles. On process loss, `awaiting_submission` or `bound` with
no delivery start settles `INTERRUPTED/NONE`. `delivery_started`,
`delivery_acknowledged`, or `released` without a terminal receipt settles
`INTERRUPTED/UNKNOWN` unless the registered authoritative domain effect receipt
proves `NONE`, the exact committed effect, or `PARTIAL`. The transient operand
is never reconstructed or resumed after owner loss.

For a Modelo edit, the domain writer consumes the exact admitted
`ModeloEditBaselineV1` and performs one atomic compare-and-swap revalidation
with the canonical encrypted mutation. Where the Modelo store and operation
journal cannot share a transaction, the writer records an idempotent effect receipt,
keyed by the operation/handoff identity but containing no financial value, in
the same transaction as the mutation; the supervisor records terminal state
from that receipt. Absence or disagreement remains `UNKNOWN`, never inferred
from a refreshed read. The canonical encrypted Modelo store is the only durable
home for committed financial values.

All runtime entries are discarded on successful consume, expiry, pre-delivery
cancellation, terminal settlement, supervisor shutdown, and owner cleanup. Raw
values and reversible derivatives are forbidden from operation requests,
journals, events, checkpoints, receipts, baselines, public projections,
diagnostics, logs, traces, temporary files, caches, exception text, content
digests, and retained frontend state. Conformance uses unique sentinel values
to scan every such surface; it excludes only the canonical encrypted value
written by the successful domain effect.

### Amendment to D0 and D6: typed result-to-Workspace refresh target

An operation definition may register one exact Workspace refresh-target model,
its `OperationSchemaIdentityV1`, and a deterministic side-effect-free domain
adapter from safe terminal subject/result facts to that model. Generic
operations owns `OperationWorkspaceRefreshTargetRequestV1` and the closed
`OperationWorkspaceRefreshTargetResultV1[RefreshTargetT]`; domain packages own
their target DTO and adapter and register them at composition. Operations never
imports Modelo, and Workspace never imports operation persistence contracts.

The request carries `refresh_target_version = 1`, operation ID, terminal
revision, definition-contract digest, and declared refresh-target schema
identity. It never accepts a caller-supplied `result_ref`. The operation service
reloads the authoritative terminal receipt, validates success/refusal,
definition digest, and registered schema, then passes only the definition-owned
safe terminal facts to the adapter. It validates the returned exact target type
and fingerprint before returning success. For Modelo, the application.modelo
registration returns a `ModeloWorkspaceRefreshTargetV1` containing only the
typed coordinates needed to issue a new Workspace request; it contains no
financial values or old baseline. Workspace remains solely responsible for
reading current owners and minting the refreshed baseline.

The refusal codes are exactly `unsupported_refresh_target_version`,
`unknown_operation`, `operation_not_terminal`, `operation_not_successful`,
`refresh_adapter_unavailable`, `definition_contract_mismatch`,
`refresh_schema_mismatch`, and `unsafe_refresh_target`. The service works after
process restart from durable safe terminal facts and registry composition. A
raw result/reference, repository DTO, route ID, TUI view model, exception, or
adapter path never crosses the facade.

### Public version separation and refusal

The public contract set has separate current-only axes:

- public-definition manifest version `1` and `contract_set_digest`;
- observation request/result/projection/event-page version `1`;
- REVIEW-projection reference/request/result version `1` and each registered
  REVIEW DTO's own schema identity;
- Workspace-refresh-target request/result version `1` and each registered
  target DTO's own schema identity;
- transient-financial-operand protocol version `1` and each registered operand
  schema identity;
- operation-definition digest and request/result/response schema identities;
- envelope revision, which orders lifecycle compare-and-swap state;
- event cursor, which orders replay; and
- durable journal schema version, which is private to persistence hydration.

None may be substituted for another or copied into a shared `version` field.
Every public endpoint parses only its minimal version header before exact model
dispatch and returns its endpoint-specific unsupported-version refusal. A
request with a supported endpoint version but mismatched definition digest or
registered schema identity refuses on that mismatch; it does not reinterpret
the payload. Pre-release breaking change replaces the relevant V1 contracts and
all in-tree producers/consumers in one cutover, deletes the old models,
dispatchers, fixtures, and tests, and regenerates the contract-set digest. No
reader, migration shim, fallback parser, or missing-field default preserves a
legacy public version. While the compatibility regime is `PRE_RELEASE`, private
durable-schema evolution follows the same current-only cutover: zero affected
nonterminal invocations, exact-version refusal, and deletion of old readers,
migrators, fixtures, and tests. A future post-release upgrade path may exist
only after the compatibility-checkpoint authority flips the regime; this
operation decision does not create or anticipate one.

### Exact C0 observation dependency receipt

After adoption, the canonical `tui-architecture` plan adds the exact C0 artifact
`.vault/reference/2026-08-24-tui-operation-observation-dependency-receipt.md`.
It validates as `TuiOperationObservationDependencyReceiptV1` under the sole
live-tree validator
`src/cadrumo/application/operations/tests/test_public_operation_dependency_receipt.py`.
No alternate path, schema alias, prose attestation, fixture-only validator, or
receipt from another commit opens C0.

The receipt is produced only from a clean implementation commit and records:

- receipt schema version, producing commit, source-tree digest, and dirty-tree
  refusal;
- governing stem `2026-08-11-tui-architecture-adr`, its `accepted` status,
  post-amendment body hash and producing commit, plus ancestry to the receipt;
- staging stem `2026-08-24-tui-operation-observation-adr`, its required
  `rejected` status and body hash, proving it is provenance rather than a second
  authority;
- public-definition manifest, observation, REVIEW resolver, and refresh-target
  endpoint versions; every registered schema identity and fingerprint; every
  definition digest; and the exact `contract_set_digest`;
- the sorted public export and observation/review/cancel/detach/respond/refresh
  capability inventories and their digests, plus production composition parity;
- real-adapter atomic observation under an interleaved transition, independent
  lifecycle/terminal/effect parity, progress folding and phase reset, bounded
  replay, cursor-ahead refusal, expiry/compaction resynchronization, detach, and
  reconnect;
- the complete public-state parity for action reference, definition, request,
  result, REVIEW, response, and refresh schema identities and digests;
- atomic invocation definition-digest pinning plus acquisition, observation,
  response, and reconciliation refusal after simulated registry drift;
- registered safe REVIEW resolution from a fresh service instance, every typed
  refusal, strict output-schema validation, and proof that resolution neither
  consumes nor grants response authority;
- a registered typed refresh-target conformance definition resolved after
  process restart, every typed refusal, and proof that no caller-supplied result
  reference or stale Workspace baseline is accepted;
- exact current-version round trips and endpoint-specific unsupported-version,
  schema-mismatch, and definition-digest refusals;
- PRE_RELEASE exact private-schema refusal, zero affected nonterminal
  invocations at a breaking cutover, deletion of superseded operation readers,
  migrators, fixtures, and tests, and replacement of the accepted parent's
  conflicting D5 migration clause; and
- forbidden imports plus sentinel non-retention across public DTOs, journal,
  events, receipts, diagnostics, traces, logs, exceptions, and persistence
  materializations.

This receipt does not claim the transient financial operand protocol exists. It
opens only the C0 operation-platform visual-projection cohort; it cannot claim
readiness for C1 read-only Modelo relocation, C2 Workspace, C3 edit, C4 action
enrollment, or C5 fixed-point cohorts.

### Exact future financial-operand dependency receipt

The operation-side prerequisite for C3 is the separate artifact
`.vault/reference/2026-08-24-tui-operation-financial-operand-dependency-receipt.md`.
It validates as `TuiOperationFinancialOperandDependencyReceiptV1` under the sole
live-tree validator
`src/cadrumo/application/operations/tests/test_financial_operand_dependency_receipt.py`.
It is not produced during C0 and cannot be replaced by the generic
ephemeral-secret conformance receipt.

Its closed predecessor tuple contains the exact C0 receipt path, schema,
producing commit, and content digest; the accepted parent's then-current body
hash; accepted stem `2026-08-24-modelo-edit-contract-adr` and its body hash; the
exact Workspace predecessor
`.vault/reference/2026-08-24-tui-registry-api-gate-c2-dependency-receipt.md` as
`ModeloWorkspaceC2DependencyReceiptV1` with producing commit and content digest;
and the implementation commit under validation. It records and proves:

- protocol version `1`, every enrolled declaration and operand schema identity,
  the affected operation-definition digests, and production registry/DI parity;
- exact type, operation, definition, revision, grant-fingerprint, baseline,
  expiry, and schema binding without content hashing;
- atomic `awaiting_submission -> bound -> delivery_started ->
  delivery_acknowledged -> released` transitions, duplicate and concurrent
  submit/consume races, and exactly one executor observation;
- expiry, pre-delivery cancellation, terminal settlement, owner cleanup, and
  supervisor-shutdown release;
- crash injection before binding, while bound, after delivery start, after
  acknowledgement, after release, and across terminal settlement, with exact
  `NONE`/`UNKNOWN` classification and domain effect-receipt narrowing;
- an enrolled Modelo writer's atomic `ModeloEditBaselineV1` compare-and-swap,
  idempotent effect receipt co-commit, stale-baseline refusal, and no refreshed
  read masquerading as effect proof; and
- unique-sentinel absence from every forbidden operation, frontend, filesystem,
  diagnostic, logging, trace, exception, receipt, digest, and cache surface,
  while allowing only the successful canonical encrypted Modelo value.

Passing this receipt opens only the operation-custody half of C3. C3 still
requires the accepted Modelo editor decision, the applicable Workspace and
interface predecessor receipts, and their own live validators. Neither receipt
opens C4 or C5.

### Canonical-plan integration

`W05.P11.S60` consumes the public service rather than supervisor
`inspect`/persistence DTOs; `S61` projects only
`OperationPublicProjectionV1`; `S62` consumes
`OperationPublicEventPageV1`; and `S63` is narrowed to registered safe REVIEW
projection and separately authorized APPLY/REJECT. The same plan schedules the
public definition manifest and refresh-target service before C0, and schedules
the transient financial operand protocol only at the future C3 dependency
step. Later interface receipts cite the exact predecessor artifacts rather than
restating their facts. No separate operation, editor, or migration plan is
created.

## Rationale

Only the application layer can observe authoritative envelope state and ordered
events without exposing persistence or making a frontend reconstruct lifecycle
truth. One atomic materialization closes the snapshot/replay race while keeping
the accepted supervisor, journal, and event stream as the sole authorities.
The public projection preserves the three accepted state axes and gives every
frontend explicit current-only version boundaries. A registered safe projector
turns a REVIEW reference into renderable facts without exporting its secure
operand or response bearer. A definition-owned result adapter provides a typed
Workspace refresh seam without teaching operations about Modelo or teaching
TUI about result references. A distinct transient-financial-operand protocol
keeps editor values out of durable operation state while recording enough
handoff and effect evidence to classify owner loss honestly. Incorporating all
of those clauses into the accepted parent preserves one authority. These are
the decisive ownership, consistency, security, and honesty criteria identified by
`2026-08-24-tui-operation-observation-research`.

## Consequences

- TUI operation work gains one frontend-safe atomic observation target without
  learning the private journal schema or secure checkpoint topology.
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
- Every public state names its exact action, definition, request, result,
  REVIEW, response, and refresh schema contracts and their deterministic
  definition/contract-set digests.
- Safe REVIEW content becomes resolvable after restart without exposing the
  encrypted operand, its digest, or a response capability.
- Successful terminal operations can yield a typed Workspace refresh target;
  Workspace still performs the new atomic read and owns the new baseline.
- Financial edit values may cross one application-memory handoff to one
  executor, but never become a resumable operand. A crash after delivery starts
  is deliberately `UNKNOWN` unless an authoritative domain receipt narrows it.
- The transient financial protocol adds operation checkpoints, registry
  declarations, domain effect-receipt integration, crash testing, and a strict
  non-retention burden; it is not part of C0.
- Input and choice interaction rendering remains blocked rather than falsely
  advertised by the initial modal.
- The accepted parent and canonical plan must be amended and the exact C0
  receipt must pass before visual operation projection begins; C3 additionally
  requires the exact financial-operand receipt and its independent predecessors.
- This record ends as rejected adoption provenance and creates no parallel
  authority or plan.
- Public-contract changes and durable journal changes can proceed independently,
  but each retains its own strict current-version cutover and conformance burden;
  while `PRE_RELEASE`, no private-schema migration path survives either cutover.
