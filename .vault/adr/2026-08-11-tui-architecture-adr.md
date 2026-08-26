---
tags:
  - '#adr'
  - '#tui-architecture'
date: '2026-08-11'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:7a3c209e34e108fa9eced71ba5b11506adc0c597939aed8f29b8b43197422dea'
related:
  - '[[2026-08-11-tui-architecture-research]]'
  - '[[2026-08-11-tui-interface-research]]'
  - '[[2026-08-11-tui-interface-adr]]'
  - '[[2026-07-23-tui-wizard-substrate-adr]]'
  - '[[2026-08-09-cli-action-envelope-hardening-adr]]'
  - '[[2026-07-24-profile-bundle-tui-adr]]'
  - '[[2026-07-25-censal-profile-autofill-adr]]'
  - '[[2026-08-08-sync-control-surface-adr]]'
  - '[[2026-08-24-tui-architecture-censo-operation-authority-reconciliation-research]]'
  - '[[2026-08-24-tui-architecture-pre-custody-login-secret-submission-research]]'
  - '[[2026-08-24-tui-architecture-pre-custody-login-secret-submission-reference]]'
  - '[[2026-08-24-tui-operation-observation-research]]'
  - '[[2026-08-24-tui-operation-observation-adr]]'
  - '[[2026-07-09-compatibility-lifecycle-adr]]'
  - '[[2026-08-10-current-schema-only-purge-adr]]'
  - '[[2026-08-26-tui-architecture-m184-socio-clave-subclave-research]]'
---
# `tui-architecture` adr: `Application-owned operation envelope and supervisor API` | (**status:** `accepted`)

## Canonical defining-module amendment

This in-place amendment replaces every facade-based import, export, promotion,
composition, migration-destination, and receipt-inventory clause in this record.
A package namespace is structural and inert: its `__init__.py` imports, binds,
aliases, lazily resolves, or re-exports no project symbol. An empty `__all__`
may document that fact. Every cross-package public symbol is defined exactly
once in a semantically named, non-underscore module, and every consumer imports
it directly from that defining module.

An underscore-private module may contain implementation used only inside its
owning package. Once a contract has a cross-package consumer, its definition and
tests hard-move to a public defining module with every production, test,
tooling, annotation, registration, dynamic target, manifest, and receipt
consumer. The former module and every package export, facade test, alias, shim,
forwarder, fallback, and compatibility path are deleted in the same atomic
relocation. Migration records name `canonical_defining_module` and
`canonical_symbol`; a package namespace is never a destination. Receipt
inventories bind defining-module symbols and their exact `__module__`, not
package exports.

The frontend-neutral operation API is the family of public defining modules
under `cadrumo.application.operations`; the package namespace itself is inert.
`_composition.py` hard-moves to `composition.py`, retaining the sole definitions
of `OperationComposedServices`, `OperationSubmission`,
`OperationSubmissionService`, and `compose_operation_services`; every consumer
moves directly and the facade is deleted atomically. Other cross-package
operation contracts follow the same rule. Persistence-facing contracts are
public only in their own defining modules when adapters consume them, and remain
private only when no cross-package consumer exists. This import topology does
not widen frontend data authority.

`ManagerAction`, `ManagerActionOutcome`, `ManagerActionDisposition`, and
`ManagerProgressSinkBinder` are retired rather than promoted. They implement
the callback architecture this ADR rejects. Profile presentation addresses work
by registered `OperationDefinitionId`, submits through the operation controller,
and observes public operation projections. No TUI worker invokes an arbitrary
business callback, owns a progress sink, or infers terminal state.

Every TUI `__init__.py` is likewise inert. `__main__` imports `launcher.main`
directly; launcher, app, and feature modules import exact defining modules such
as `components.widgets`, `operations.controller`, and `profile.sync_review`.
Feature packages do not republish one another.

`TuiCapability.AVAILABLE` requires a callable implementation in the canonical
`cadrumo.entrypoints.tui` tree. No command remains available through
`cadrumo.adapters.inbound.tui` or another legacy seam. An unmigrated command is
`NOT_IMPLEMENTED`; explicit `--tui` never falls back to line mode.

## Problem Statement

Frontend-triggered application work has no canonical execution boundary. The
TUI owns worker lifetimes, busy state, progress prose, interaction handoff, and
terminal presentation while opaque callbacks independently own effects,
persistence, deadlines, and cleanup. Extending any frontend mechanism would
preserve this split and require each future tool call to reconstruct the same
safety contract.

This record establishes one application-owned operation envelope and
`OperationSupervisor` API. TUI, CLI, and MCP remain projections over that
authority. The defect and option boundary are grounded in
`2026-08-11-tui-architecture-research`; census synchronization is a mandatory
acceptance scenario, not the architecture's scope or vocabulary.

This is the backend architecture required to make a future TUI safe and
expressive. It does not decide the holistic frontend information architecture,
screen hierarchy, navigation model, wizard composition, or final visual
component catalogue. A parallel frontend ADR may decide those concerns, but it
must conform to this record's canonical `cadrumo.entrypoints.tui` placement and
`components` naming rather than create a competing package root.

## Considerations

- Stable action identity, precondition evidence, and recovery references already
  belong to the application action catalogue; this decision must compose them,
  not create a competing catalogue
  (`2026-08-09-cli-action-envelope-hardening-adr`).
- The CLI envelope is a terminal wire projection, not an internal dispatcher
  (`2026-06-10-cli-envelope-notice-standardisation-adr`).
- MCP confirmation and process controls are transport-level defense in depth;
  they cannot manufacture application approval
  (`2026-06-30-agent-harness-adr`).
- Lifecycle position, terminal condition, and committed effect answer different
  questions and must remain independently representable
  (`2026-08-11-tui-architecture-research`).
- Cancellation, deadlines, durability, resumability, and resource ownership are
  capabilities, not promises every executor can honestly make
  (`2026-08-11-tui-architecture-research`).
- A frontend-safe observation must bind current snapshot state, ordered event
  history, progress, and replay to one atomic anchor; a frontend cannot
  reconstruct that authority from separate supervisor calls
  (`2026-08-24-tui-operation-observation-research`).
- REVIEW observation, safe REVIEW content, and response bearer authority are
  separate contracts. Observation must never recreate apply/reject authority
  (`2026-08-24-tui-operation-observation-research`).
- A transient financial edit operand requires typed, baseline-bound,
  single-consumer custody distinct from generic secret submission, persistent
  secure lookup, and `OperationDurability.EPHEMERAL`
  (`2026-08-24-tui-operation-observation-research`).
- A generic terminal result reference cannot be interpreted as a Workspace
  target; the operation definition must register a safe typed adapter
  (`2026-08-24-tui-operation-observation-research`).
- Public manifest, observation, REVIEW, Workspace-refresh, operand, envelope,
  cursor, and private journal versions answer different questions and cannot
  share one version axis (`2026-08-24-tui-operation-observation-research`).

## Considered options

- **Expand `ManagerAction` and `ManagerActionOutcome`.** Rejected because it
  retains execution authority in Textual and leaves credential, CLI, and MCP
  lifecycles separate.
- **Share events while retaining raw frontend callbacks.** Rejected because it
  improves rendering without owning interaction, cancellation, concurrency,
  cleanup, or settlement.
- **Use the CLI `SchemaEnvelope` as the internal bus.** Rejected because that
  versioned terminal wire contract carries CLI projection concerns and does not
  supervise work.
- **Create independent domain or frontend supervisors.** Rejected because it
  preserves duplicated lifecycle authority.
- **Application-owned operation envelope plus `OperationSupervisor`.** Chosen.
  Domain executors retain policy and effect ownership; one application service
  owns invocation, observation, interaction, cancellation, deadlines, cleanup,
  and settlement; frontends project its typed state.

## Constraints

- Operation execution identity and recovery-action identity are distinct.
  Operation definitions MUST NOT be keyed by `ActionReference`; they may carry
  an optional validated `ActionReference` only when an existing recovery or
  next-action verdict actually dispatches that operation.
- The application envelope MUST contain no localized prose, CLI path, terminal
  formatting, Textual worker identity, transport token, spinner state, or secret
  value.
- Every operation type MUST declare durability, cancellation, deadline,
  idempotency or replay, baseline, sensitive-input, conflict-scope, and owned
  resource capabilities. Omission is invalid, not permissive.
- A terminal condition MUST NOT be published while executor work or resource
  cleanup can still change the effect axis.
- `CANCELLED` and `TIMED_OUT` MUST mean execution stopped and cleanup settled;
  cancelling an observer, wrapper worker, or countdown cannot produce either.
- Secret-bearing interaction values MUST remain within secure custody and MUST
  NOT enter journals, diagnostics, events, approval digests, or projections.
- Public operation models MUST be strict, frozen, discriminated,
  renderer-neutral, and free of persistence DTOs, raw exceptions, secure
  references, localized prose, callbacks, and untyped payload bags.
- Initial public interaction observation supports only `REVIEW` plus separately
  authorized `APPLY` and `REJECT`. `INPUT` and `CHOICE` remain unavailable until
  their response and custody contracts are separately accepted and proven.
- While the repo-committed compatibility regime is `PRE_RELEASE`, private
  operation schemas accept only the current shape. Breaking cutover requires
  zero affected nonterminal invocations and deletion of superseded readers,
  migrators, fixtures, and tests; this ADR cannot authorize a post-release
  upgrader.
- Financial operands and reversible derivatives MUST NOT enter operation
  requests, journals, events, checkpoints, receipts, public projections,
  diagnostics, traces, temporary files, caches, exception text, content
  digests, or retained frontend state. Only the canonical encrypted domain
  effect may retain a committed financial value.
- Unsafe interruption windows MUST declare cancellation unsupported until the
  operation can stop without violating its domain invariants.
- The accepted action identity, wizard-state, and CLI projection contracts are
  stable parents. The supervisor does not depend on evolving MCP SDK hooks.

## Implementation

### D0 - Scope and topology authority

This ADR owns the frontend-neutral operation backend, its persistence and
composition ports, and the narrow
`cadrumo.entrypoints.tui.operations` projection needed to observe and control
that backend. The `tui-interface` concern owns the TUI shell, `components`,
profile, secret, flow, Modelo, testing, navigation, information architecture,
screen grouping, and visual composition. Neither concern may move application
policy into the TUI.

This accepted ADR is the topology authority. The canonical frontend home is
`src/cadrumo/entrypoints/tui/`, with `components`, `operations`, `profile`,
`secret`, `flows`, and reserved `modelo.view` and `modelo.edit`. A top-level
`cadrumo.tui`, a top-level `cadrumo.bootstrap`, nested `entrypoints.tui.core`,
`shared`, and generic `surfaces` packages are prohibited. Related frontend
decisions conform to this tree and do not reopen its root or naming.

The sole frontend-neutral operation API is the public
`cadrumo.application.operations` facade. Persistence-facing ports and records
remain application-owned implementation contracts for adapters. An inbound
frontend may neither import nor receive `OperationPersistedSnapshot`,
`OperationJournalRecord`, raw `OperationEvent`,
`OperationPendingInteraction`, or `OperationConsumedInteraction`. TUI, CLI,
MCP, and future frontends consume only the versioned public observation,
REVIEW-projection, response, cancellation, detach, and Workspace-refresh
services. Entry points never call transient-financial-operand custody directly;
the owning domain application service performs that handoff inside one
application-owned submission flow.

### D0a - Existing-capability reuse ledger

The operation platform fills the missing supervision layer and MUST compose,
not redeclare, these existing authorities:

- `cadrumo.application.operator_actions` retains recovery-action identity,
  binding provenance, and action catalogue authority. Operations add a distinct
  definition identity and only an optional join.
- `cadrumo.core.observability` retains run correlation, redacted log capture,
  retention, and diagnostic envelope authority. Operations contribute lifecycle
  events and references, not a second logging system.
- `cadrumo.application._journal_repository.JournalRepositoryBase` remains the
  hardened credential-free atomic file substrate. The operation journal adds a
  typed port, transition protocol, and lease semantics over it.
- Reset and profile-bundle publication records retain their domain-specific
  lifecycle and reconciliation rules. Generic supervision references or adapts
  them; it does not copy their models into `application.operations`.
- Workflow run persistence and the renderer-neutral `application.flows` engine
  retain workflow/checkpoint and wizard-state authority. An operation may invoke
  or observe them but cannot reinterpret a workflow or wizard transition as an
  operation lifecycle transition.
- `application.storage.sync_runs.SyncRunRecord` retains completed sync-surface
  provenance. It is linked from an operation receipt and never promoted into the
  generic in-flight journal.
- Existing auth acquisition locks, browser/session lifecycle contexts, atomic
  storage writers, and domain event commits remain executor-owned safety
  primitives. The supervisor owns their enclosing resource scope and terminal
  settlement without replacing their local invariants.

The implementation plan must cite the reused symbol for every capability above
and may introduce a new primitive only when a focused code census proves that no
existing authority supplies the required semantics.

### D1 - Canonical operation envelope

Introduce a strict application-owned `OperationEnvelope`, identified by an
immutable invocation `operation_id` and a stable `OperationDefinitionId`. It
carries a validated typed request, operation revision, capability declaration,
safe context references, three state axes, typed phase, pending interaction,
deadline state, reviewable outcome or proposal reference, terminal result or
refusal reference, redacted diagnostic reference, ordered event cursor, and
journal metadata when durability is enabled. A definition may reference an
existing canonical `ActionReference`, but that relationship is optional and is
never the operation's identity. Domain-specific requests, proposals, baselines,
and results remain domain-owned payloads registered with the operation
definition.

The envelope schema is stable and closed at the generic lifecycle boundary but
extensible through versioned registered request, result, phase, interaction,
event-detail, and review-payload families. Extensions cannot add new generic
state meanings by smuggling them into free-form fields.

Submission pins the selected operation definition contract digest in the same
atomic transition as the request reference and initial lifecycle event. That
pin is invocation identity: resume, observation, REVIEW resolution, response,
Workspace-refresh resolution, and reconciliation all require the current
registry definition to reproduce it.

### D2 - Independent lifecycle, terminal, and effect axes

The global lifecycle is `CREATED`, `QUEUED`, `RUNNING`,
`WAITING_FOR_INTERACTION`, `WAITING_FOR_EXTERNAL`,
`CANCELLATION_REQUESTED`, `SETTLING`, or `TERMINAL`.

The terminal condition is absent until terminal, then exactly one of
`SUCCEEDED`, `REFUSED`, `FAILED`, `CANCELLED`, `TIMED_OUT`, or `INTERRUPTED`.
The effect is independently `NONE`, `UPDATED`, `PARTIAL`, or `UNKNOWN`.
Operation-specific phases are typed codes below the global lifecycle and are
localized only by frontend projections.

### D3 - Supervisor API and settlement ownership

The application exposes `submit`, `start`, `observe`, `stream_events`,
`respond`, `request_cancel`, `await_terminal`, and `reconcile`. Observation is
revisioned and event streaming is ordered and cursor-based, so an asynchronous
consumer can detach, reconnect, replay missed events, and resume live feedback
without restarting work. Only the supervisor may advance the generic lifecycle,
enforce the aggregate deadline, publish terminal settlement, or close the owned
resource scope. Executors emit typed phase, interaction, log, effect, and result
facts through a supervisor context; they do not mutate the envelope directly.

`OperationEvent` is a discriminated, monotonically sequenced record carrying the
operation identity, envelope revision, timestamp, event kind, stable code, and
safe typed facts. `OperationLogRecord` is a structured event variant with
severity and optional redacted diagnostic correlation. Localized log lines and
status copy are projections. Retention and persistence follow the operation's
declared durability policy; secrets are rejected at the event boundary.
Streaming MUST define bounded buffering, cursor expiry, replay, and slow-consumer
behavior without allowing backpressure to stall or corrupt the operation.

This event model does not replace `cadrumo.core.observability`. Each operation
opens or joins the existing run/log capture scope and records the resulting
redacted diagnostic reference and correlation identity. Operation events carry
safe lifecycle facts and log references; the observability subsystem remains the
authority for diagnostic log capture, retention, and envelope capture.

Cleanup is part of settlement. Browsers, sessions, locks, files, child
processes, and similar resources belong to the operation scope. The lifecycle
enters `SETTLING` after execution and reaches `TERMINAL` only after resources
are released or cleanup failure is recorded. Closing a frontend detaches its
projection; it does not assert that the operation stopped.

`observe` and `stream_events` are supervisor/application implementation seams,
not frontend DTO boundaries. The public facade instead accepts
`OperationObservationRequestV1`, containing observation version `1`, operation
identity, exclusive `after_cursor`, and a bounded page limit, and returns the
closed `OperationObservationResultV1`. Success contains one
`OperationPublicProjectionV1` and one `OperationPublicEventPageV1` for the same
anchor; refusal is typed and renderer-neutral. The service parses only a
minimal version header before exact request dispatch. Unsupported versions
return `unsupported_operation_observation_version`; unknown operation,
cursor-ahead, invalid cursor, and observation-unavailable conditions likewise
return typed safe refusals. Raw validation, repository, and persistence
exceptions never cross the facade.

One internal observation-read port returns an application-owned materialization
from a single persistence read. It binds the current internal snapshot and
envelope revision, authoritative anchor cursor, bounded history slice requested
after the caller cursor, fold input or checkpoint needed to derive progress
through that anchor, and replay status plus restart cursor when retained history
cannot continue the caller's fold. The persistence adapter obtains all of those
facts from one atomic journal-record read. The application projector rejects a
materialization whose event identity, revision, sequence, or cursor exceeds or
disagrees with the anchor. A later commit may make the result stale, but cannot
make it internally inconsistent.

The application fold begins with no progress, clears progress on phase change,
and replaces it with each progress event through the anchor cursor. A future
compaction implementation must persist or derive an equivalent fold checkpoint
before returning `expired` or `compacted`; it may not drop current progress or
ask a frontend to reconstruct pre-retention history. Notices, logs, and
diagnostics remain ordered page records rather than current lifecycle fields.

### D3a - Credential-free request identity and ephemeral secret submission

The supervisor has two explicit, mutually exclusive request-storage policies.
`SECURE_REFERENCE` retains the current encrypted content-addressed operand
path. `CREDENTIAL_FREE_JOURNAL` is allowed only for a registry-validated,
strict, safe request model and is atomically recorded with the lifecycle
snapshot; its canonical content digest binds idempotency. It is not a fallback
encrypted store and may never hold a secret, reversible secret derivative,
callback, frontend identity, or transport bearer. This policy supplies the
durable exact target for an operation that must obtain a secret before a DEK
exists; no executor may reconstruct a special request from its subject as an
alternative persistence path.

The application operation facade exposes one `EphemeralSecretSubmission` port,
owned by the same supervisor that owns the operation. A definition that declares
the capability supplies a durable, credential-free secret requirement containing
only the operation identity, definition, subject, interaction identity and
revision, secret kind, and expiry. The port accepts a runtime-only secret input
only when that exact requirement is live; it refuses mismatch, stale revision,
expiry, duplicate submission, or an already-consumed requirement. The broker
retains the input only in process memory, binds it to that requirement, consumes
it once for the registered executor, and zeroises it on consume, expiry,
cancellation, terminal settlement, supervisor shutdown, and owner cleanup.
Neither the input nor a digest or callback derived from it enters an envelope,
journal, event, receipt, diagnostic, response, projection, trace, or retained
frontend state.

A created secret-wait is a pre-effect state. If restart reconciliation proves
that no runtime broker secret survives and no executor entry was recorded, the
supervisor settles it `INTERRUPTED` with effect `NONE`; it does not resume,
re-prompt, derive, or retain the secret. Once executor entry is recorded, the
ordinary owner-loss rule remains `UNKNOWN` unless the executor's authoritative
domain receipt proves a narrower effect. Requirement expiry and pre-entry
cancellation clear the broker and settle with effect `NONE`; expiry is a secret
submission bound, not an aggregate execution deadline. This is a generic
supervisor capability, not a profile-login exception. Its conformance suite
must prove exact binding, single consumption, every refusal, cleanup,
non-retention, pre-entry restart interruption, and post-entry uncertainty.

This generic byte-oriented secret broker does not authorize financial editing.
The distinct current-only `OperationTransientFinancialOperandProtocolV1` is a
typed, definition-declared custody protocol for an already validated financial
operand. It is explicitly not `OperationDurability.EPHEMERAL`,
`EphemeralSecretSubmission`, or persistent `OperationSecureOperandLookup`.
An opting-in definition binds one
`OperationTransientFinancialOperandDeclarationV1`: exact typed operand model
and schema identity, maximum lifetime, exact edit-baseline schema identity,
reconciliation policy `INTERRUPT`, and an authoritative domain effect-receipt
resolver. Registry construction permits it only for `RECORDED` operations that
declare effect `NONE`, `UNKNOWN`, and every domain effect the writer can prove.

An owning domain edit application service submits through
`OperationTransientFinancialOperandSubmissionV1`; no entrypoint receives or
retains the custody grant. The service creates or resolves the exact
credential-free operation and receives a runtime-only 256-bit submission grant
from the supervisor. The grant remains within that application call, is never
serialized or returned to a frontend, and is discarded after success or
refusal. Durable `OperationTransientFinancialOperandRequirementV1` contains
only operation and definition identity, invocation revision, a fingerprint of
fresh random grant material, operand schema identity, the declaration's
edit-baseline schema identity, a safe opaque domain edit-baseline reference,
and expiry. It contains no operand value or content-derived digest. For Modelo,
the reference identifies `ModeloEditBaselineV1`; a Workspace read baseline is
never accepted as a substitute.

The supervisor owns one in-memory entry per exact requirement and serializes
submission, consumption, cancellation, expiry, and settlement under the same
operation transition lock. It validates the registered concrete operand type
without serializing or hashing values, takes the sole strong custody reference,
and atomically advances the durable custody checkpoint from
`awaiting_submission` to `bound`. Wrong type, definition, schema, operation or
revision, expired grant, duplicate submission, duplicate consumption, and an
already terminal operation are typed refusals. The submitting scope drops its
operand and grant references after transfer.

Only the registered executor receives
`OperationTransientFinancialOperandAccessV1`. One consume attempt durably
advances `bound -> delivery_started` before the broker removes its entry, then
`delivery_started -> delivery_acknowledged` when the executor accepts the
guarded value. No second consumer can observe it. Exiting the guarded scope
drops supervisor and executor custody references and advances to `released`;
release proves custody cleanup, not an effect. Mutable backing buffers are
zeroised where the declared model provides them, while the implementation makes
no false claim that immutable Python object memory can be reliably erased.

Expiry before `delivery_started` discards the runtime entry and settles
`INTERRUPTED` with effect `NONE`; expiry is a submission bound, not an aggregate
execution deadline. Pre-delivery cancellation discards the entry and settles
`CANCELLED/NONE` only after supervisor acknowledgement and cleanup. After
`delivery_started`, expiry cannot revoke executor access and cancellation cannot
claim a terminal outcome until the executor or reconciliation settles. Process
loss in `awaiting_submission` or `bound` with no delivery start settles
`INTERRUPTED/NONE`. Process loss in `delivery_started`,
`delivery_acknowledged`, or `released` without a terminal receipt settles
`INTERRUPTED/UNKNOWN` unless the registered authoritative domain effect receipt
proves `NONE`, the exact committed effect, or `PARTIAL`. The operand is never
reconstructed or resumed after owner loss.

For an enrolled Modelo edit, the domain writer consumes the exact admitted
`ModeloEditBaselineV1` and performs one atomic compare-and-swap revalidation
with the canonical encrypted mutation. Where the Modelo store and operation
journal cannot share one transaction, the writer records an idempotent effect
receipt keyed by operation and handoff identity, containing no financial value,
in the same transaction as the mutation; the supervisor settles from that
receipt. Absence or disagreement remains `UNKNOWN`, never inferred from a
refreshed read. The canonical encrypted Modelo store is the sole durable home
for committed financial values.

All runtime entries are discarded on successful consume, expiry, pre-delivery
cancellation, terminal settlement, supervisor shutdown, and owner cleanup.
Conformance scans unique sentinel values across every forbidden operation,
frontend, filesystem, diagnostic, logging, trace, exception, receipt, digest,
and cache surface, excluding only the canonical encrypted value written by the
successful domain effect.

### D4 - Typed interaction and exact approval binding

Operator interaction is a discriminated application contract, not a frontend
callback. A request carries immutable interaction and operation identities, an
operation revision, response schema, safe presentation facts, optional expiry,
and a digest of the exact state it continues. Responses are single-use; stale,
duplicated, mismatched, or expired responses are refused.

Approval is a specialized interaction. It binds the exact request, baseline,
reviewed proposal, proposed effect digest, actor, and time. Execution consumes
that approved operand and MUST NOT silently re-read, rebuild, or substitute a
different proposal. A changed baseline returns to typed review or settles as a
stale refusal according to domain policy.

An asynchronous executor may publish a typed `REVIEW_READY` interaction with a
reviewable proposal or provisional outcome while remaining
`WAITING_FOR_INTERACTION`. The generic response API carries explicit `APPLY` or
`REJECT` intent, plus operation revision and proposal digest. `APPLY` resumes the
registered effect phase using exactly that operand; `REJECT` records a typed
rejection result and settles with no governed effect. A proposal is never
reported as the authoritative terminal result before this continuation settles.

Public pending-interaction observation is discriminated as `none`,
`review_available`, or `unsupported`. `review_available` carries only safe
operation and interaction identities, operation revision, presentation and
response-schema codes, expiry, and
`OperationReviewProjectionReferenceV1`. That reference contains only operation
ID, interaction ID, operation revision, REVIEW-projection schema identity,
definition-contract digest, and expiry. Neither form carries a response token
or digest, persistence or secure-operand reference, reviewed operand, baseline
or proposed-effect digest, continuation material, or consumed checkpoint.

Caller-independent observation states whether the registered definition
supports the response family and whether the interaction is current. Possession
of response authority remains separate: the secure response service validates
a runtime-only bearer against exact operation, interaction, revision, proposal,
actor, and expiry. Apply/reject controls are available only when that service
confirms the bearer and the projected interaction remains current. Observation
after detach or from a fresh process cannot recreate response authority.
`INPUT` and `CHOICE` project `unsupported` with a stable code while lifecycle,
phase, progress, cancellation, and settlement remain observable.

The independent `OperationReviewProjectionRequestV1` carries minimal header
`review_projection_version = 1` plus the safe reference.
`OperationReviewProjectionResultV1` is a closed success/refusal union. Success
is `OperationReviewProjectionSuccessV1[ReviewProjectionT]`, specialized by the
definition's exact safe REVIEW model and echoing its schema identity and
definition digest.

Every definition declaring `REVIEW` binds exactly one strict safe REVIEW type,
`OperationSchemaIdentityV1`, and side-effect-free projector from the internally
resolved reviewed operand and current interaction facts. Registry construction
rejects a REVIEW definition without that triple. The operation-owned resolver
reloads the authoritative operation and pending checkpoint; validates operation,
interaction, revision, expiry, definition digest, and schema identity; resolves
the encrypted reviewed operand only behind the secure application port;
validates its registered private type; invokes the projector; validates the
exact public type and schema fingerprint; and then drops its local operand
reference. A projector may emit explanatory safe facts but never financial
values, secure references, operand or content digests, continuation or response
material, repository identity, or localized prose.

The exact refusal codes are `unsupported_review_projection_version`,
`unknown_operation`, `review_not_pending`, `stale_review_reference`,
`review_expired`, `definition_contract_mismatch`, `review_schema_mismatch`, and
`review_projection_unavailable`. Raw validation, decryption, repository, and
projector failures collapse to the last safe refusal plus a redacted diagnostic
reference. Resolution is read-only: it does not consume the checkpoint or
change expiry, lifecycle, revision, or response capability. `APPLY` and
`REJECT` still require the separate exact secure response bearer and current
revision.

### D5 - Declared durability, cancellation, and deadlines

Each operation declares `EPHEMERAL`, `RECORDED`, or `RESUMABLE` durability.
Ephemeral mode is permitted only when lost observation cannot conceal an effect
requiring reconciliation. Completed domain provenance may be referenced by a
terminal operation but does not replace lifecycle persistence.

Cancellation is `UNSUPPORTED`, `COOPERATIVE`, or `CONTAINED`. Cooperative
executors receive a cancellation scope and acknowledge safe stopping; contained
executors run behind a supervisor-owned task or process boundary that can be
stopped and reaped. Cancellation request and completion remain distinct.
Deadlines are absent, cooperative, or enforced. A displayed countdown derives
from supervisor state and cannot itself settle an operation.

Durable operation transitions use one optimistic revision and one atomic
snapshot-plus-event append. `submit` accepts an idempotency key scoped to the
definition and subject; replay returns the existing invocation. Before an
executor starts, the supervisor atomically claims the declared conflict scope
through a renewable owner lease. Only the current lease owner may advance the
envelope or perform effects. Lease expiry does not authorize immediate replay:
`reconcile` first proves owner loss, classifies any uncertain effect, and either
resumes from a declared checkpoint or settles `INTERRUPTED`.

Recorded private schemas carry an explicit current version marker. While the
repo-committed compatibility regime is `PRE_RELEASE`, acquisition refuses every
non-current private shape. A breaking definition or private-schema cutover must
first prove there are zero affected nonterminal invocations, then delete the
superseded private request, interaction, and journal readers, migrators,
fixtures, and tests. It may not translate a stored invocation or rewrite only
its definition digest. A current-shape invocation whose definition digest no
longer matches refuses acquisition and enters normal reconciliation; a
non-current shape fails at hydration and is never interpreted or reconciled as
current. A future post-release upgrade path may exist only after the accepted
compatibility-checkpoint authority flips the regime; this operation decision
does not create or anticipate one.

Event delivery is at-least-once by cursor; envelope revisions and event sequence
numbers make duplicates detectable. The journal transition, lease transition,
and effect receipt boundary MUST be specified per executor wherever they cannot
share one atomic store. The supervisor is the sole orphan-reconciliation
authority.

Cancellation and deadline settlement follow these rules:

- cooperative cancellation reaches `CANCELLED` only after executor
  acknowledgement and cleanup settlement;
- contained-process cancellation reaches `CANCELLED` only after process-tree
  termination, reaping, and cleanup settlement;
- a non-cooperative thread or external owner that may still run cannot settle
  `CANCELLED` or `TIMED_OUT`; it remains `CANCELLATION_REQUESTED` or `SETTLING`
  until reconciliation proves its state;
- an aggregate execution deadline requests cancellation, while a separate
  cleanup deadline controls escalation and orphan classification;
- owner loss or cleanup uncertainty settles `INTERRUPTED` with effect `UNKNOWN`
  unless an authoritative receipt proves a narrower effect;
- application shutdown requests the declared policy, waits through its bounded
  settlement window, persists remaining ownership state, and never derives an
  operation terminal state from frontend teardown.

### D6 - Canonical operation registry

One application registry, keyed by `OperationDefinitionId`, binds request and
result schemas, executor factory, phase and interaction families, approval and
baseline policy, request-storage and ephemeral-secret-submission policy,
transient-financial-operand declaration, capabilities, effect and idempotency
semantics, reconciliation policy, safe REVIEW projector, optional
Workspace-refresh adapter, and permitted frontend projections. It does not
extend or duplicate the operator-action catalogue. An optional join table maps
an existing `ActionReference` to an operation definition only where a validated
recovery action launches that operation.

The registry publishes `OperationSchemaIdentityV1` and
`OperationPublicDefinitionContractV1`. A schema identity contains one stable
schema ID, positive schema version, and SHA-256 fingerprint of the canonical
closed JSON schema. A public definition contract contains manifest version `1`,
`OperationDefinitionId`, nullable canonical `ActionReference`, request and
nullable result schema identities, nullable safe REVIEW-projection and
interaction-response schema identities, nullable Workspace-refresh-target
schema identity, safe declarations for interaction, request storage,
transient-financial-operand custody, durability, cancellation, deadline,
reconciliation, effect, and permitted frontend projection, plus
`definition_contract_digest` over the canonical ordered value excluding the
digest itself.

Each schema identity binds one exact strict Pydantic model and its
`model_json_schema()` fingerprint. Construction rejects duplicate IDs,
duplicate `(schema ID, version)` pairs with different fingerprints, missing
declared models, undeclared projectors or adapters, and a manifest whose digest
does not reproduce. Domain-owned models, projectors, and adapters bind through
public protocols at composition; `cadrumo.application.operations` never
statically imports the domain package. Python module, class, callable, and
adapter-path names and raw JSON schemas are not manifest fields.

`OperationPublicContractSetV1` is the canonical sorted inventory of every
public definition contract and carries deterministic `contract_set_digest`.
The inventory, each definition digest, and every schema fingerprint are
fixed-point checked against live registry composition. A registered request,
result, REVIEW, response, or refresh schema changes only by current-version
replacement of its identity plus new definition and contract-set digests; it
cannot drift behind an unchanged ID.

TUI, CLI, and MCP dispatch registered operations through the supervisor. They
may use different presentation and waiting strategies, but none may invoke an
executor, outbound adapter, or mutating business callback directly.

An operation definition may register one exact Workspace-refresh-target model,
its `OperationSchemaIdentityV1`, and a deterministic side-effect-free
domain-owned adapter from safe terminal subject/result facts to that model.
The operations package owns `OperationWorkspaceRefreshTargetRequestV1` and closed
`OperationWorkspaceRefreshTargetResultV1[RefreshTargetT]`; domain packages own
their target DTOs and adapters and register them at composition. Operations
never imports Modelo, and Workspace never imports operation persistence
contracts.

The refresh request carries `refresh_target_version = 1`, operation ID,
terminal revision, definition-contract digest, and declared target schema
identity. It never accepts a caller-supplied `result_ref`. The operation service
reloads the authoritative terminal receipt, validates success/refusal,
definition digest, and registered schema, passes only definition-owned safe
terminal facts to the adapter, and validates the returned exact target type and
fingerprint. For Modelo, application composition registers
`ModeloWorkspaceRefreshTargetV1`, containing only typed coordinates for a new
Workspace request and no financial value or old baseline. Workspace remains the
sole owner of the new authoritative read and baseline.

The exact refresh refusals are `unsupported_refresh_target_version`,
`unknown_operation`, `operation_not_terminal`, `operation_not_successful`,
`refresh_adapter_unavailable`, `definition_contract_mismatch`,
`refresh_schema_mismatch`, and `unsafe_refresh_target`. Resolution works after
process restart from durable safe terminal facts and live registry composition.
A raw result/reference, repository DTO, route ID, TUI view model, exception, or
adapter path never crosses the facade.

An operation definition may additionally register a public result schema
distinct from its private `result_type`, together with a side-effect-free
`result_projector` binding the resolved private result and the safe terminal
receipt to that public model -- symmetric with the `reviewed_operand_type`
plus `review_projector` pair, but for the settled result instead of the
mid-flight REVIEW proposal. Registration is a strict either/or on schema
identity: a public result schema that binds the exact same model as
`result_type` declares no projector, and a public result schema binding any
other model requires exactly one. No operation may bind its own private
`result_type` as its public schema AND separately declare a projector for it
-- that would be a passthrough re-admitting the private type under cover of
the public one, not a genuine projection.

`OperationResultProjectionService` resolves this door: given an operation ID,
its terminal revision, definition-contract digest, and declared result-schema
identity, it reloads the authoritative terminal receipt, refuses unless a
settled result reference is present (the accepted terminal-reference
invariant permits one on `SUCCEEDED` and permits, but does not require, one on
`FAILED`; it forbids one on `REFUSED`), resolves the encrypted private result
behind the secure operand port, validates its registered private type,
invokes the projector, and validates the exact public type and schema
fingerprint before returning it. The private result type never crosses this
boundary; only the projector's public output does. The exact refusal codes are
`unsupported_result_projection_version`, `unknown_operation`,
`operation_not_terminal`, `operation_not_successful`, `stale_operation_revision`,
`definition_contract_mismatch`, `result_schema_mismatch`, and
`result_projection_unavailable`. `OperationComposedServices` exposes this
service alongside `review` and `refresh` as `result`.

### D7 - Surface projections

The TUI consumes `OperationPublicProjectionV1` and
`OperationPublicEventPageV1`, then renders lifecycle, phase, interaction,
progress, structured live logs, cancellation availability, deadline, reviewable
outcome, apply/reject affordances, effect, and terminal state. Spinner visibility
is derived from the public projection's executing or settling lifecycle and
stops only on an authoritative waiting or terminal state. Textual workers and
stream connections may relay observation but are never operation state.

`OperationPublicProjectionV1` contains observation schema version, operation
and definition identities, nullable canonical action reference, envelope
revision, and anchor cursor; the exact `OperationPublicDefinitionContractV1`
with request, nullable result, nullable REVIEW-projection, nullable interaction-
response, and nullable Workspace-refresh-target schema identities, its
`definition_contract_digest`, and the containing `contract_set_digest`;
lifecycle, nullable terminal condition, effect, phase code, start and update
times; nullable current progress with completed, total, unit code, phase code,
event sequence, and envelope revision; declared close policy, cancellation
capability and current availability, cancellation request/acknowledgement, and
execution and cleanup deadlines; a discriminated pending interaction; terminal
result or refusal reference only when settlement provides it; and a redacted
diagnostic reference, never diagnostic prose.

Schema identities and digests are compatibility facts, not payload or response
authority. Projection refuses when the definition is absent from the current
contract set, the invocation's recorded definition digest cannot be validated,
or registered schema identities disagree with its projector. Lifecycle,
terminal condition, and effect preserve the accepted enums and validation
relationship. Spinner, terminal copy, controls, countdown, and colours remain
frontend derivations. Declared cancellation capability remains separate from
`cancellable_now` inside an irreversible section.

`OperationPublicEventPageV1` echoes the observation anchor, requested cursor,
status, ordered safe events, next cursor, and nullable restart cursor. Status is
`page`, `caught_up`, `expired`, or `compacted`; unknown operation is a result
refusal. A page is contiguous and ends at `next_cursor`. `expired` and
`compacted` carry no event rows, advance to an authoritative restart cursor,
and require the consumer to replace event-derived local state with the
accompanying projection before continuing. No event row may exceed the
projection's anchor cursor.

The public contract set has separate current-only axes:

- public-definition manifest version `1` and `contract_set_digest`;
- observation request/result/projection/event-page version `1`;
- REVIEW-projection reference/request/result version `1` and each registered
  REVIEW DTO's schema identity;
- Workspace-refresh-target request/result version `1` and each registered
  target DTO's schema identity;
- transient-financial-operand protocol version `1` and each registered operand
  schema identity;
- operation-definition digest and request/result/response schema identities;
- envelope revision for lifecycle compare-and-swap;
- event cursor for replay; and
- private durable journal schema version for persistence hydration.

None may substitute for another or be copied into a shared `version` field.
Each public endpoint parses only its minimal version header before exact model
dispatch and returns its endpoint-specific unsupported-version refusal. A
supported endpoint version with mismatched definition digest or registered
schema identity refuses; it is never reinterpreted. A pre-release breaking
public change replaces the current V1 contracts and all in-tree producers and
consumers in one cutover, deletes old models, dispatchers, fixtures, and tests,
and regenerates the contract-set digest. No reader, migration shim, fallback
parser, or missing-field default preserves a retired public version.

The CLI may synchronously submit and await, then project the authoritative
terminal result through its existing success/error envelope, notice, text, and
exit-code contracts. MCP may relay progress and cancellation through transport
facilities, but transport timeout or disconnection cannot falsely settle the
application operation.

The CLI exposes one root-owned global `--tui` request before command execution. After
the complete path is resolved, `TuiCapability.AVAILABLE` means a real callable
full-screen interface exists today and is invoked; `NOT_IMPLEMENTED` returns the
localized typed `TUI_NOT_IMPLEMENTED` refusal. Explicit `--tui` never falls back to
line mode. Help, version, completion, and equivalent introspection take precedence.

Availability and migration state are separate facts. Until the dedicated
`cadrumo.entrypoints.tui` launcher replaces them, the existing bounded CLI consumers
of `cadrumo.adapters.inbound.tui` remain authorized for commands marked `AVAILABLE`.
No new legacy consumer may be added. This transitional exception does not satisfy any
dedicated-launcher, packaging, reverse-consumer, legacy-deletion, or campaign-close gate.

### D7a - Generic operation modal

`OperationModal` is the operation-agnostic Textual projection of
`OperationPublicProjectionV1` and `OperationPublicEventPageV1`. The host owns
mounting, focus, and the public observation subscription; the supervisor owns
the operation, executor task or contained process, interactions, resources,
deadline, cancellation, effects, and settlement. The modal holds only operation
ID, event cursor, latest public revision, pending interaction ID, and
render-local state.

The modal derives phase, progress, structured logs, safe REVIEW content,
spinner, enabled controls, cancellation availability, effect, and terminal copy
only from public DTOs and the registered safe REVIEW resolver. It MUST NOT
inspect supervisor snapshots, journals, raw operation events, or persistence
checkpoints; execute business work; translate Textual worker state into
operation state; retain a business result as authority; close an operation
resource; or kill a subprocess directly.

The operation definition declares one close policy:

- `DETACH_ALLOWED`: close unsubscribes and the operation remains observable and
  reopenable by operation ID.
- `REQUEST_CANCEL`: close intent issues `request_cancel` and the modal remains
  attached through cancellation acknowledgement and settlement.
- `BLOCK_UNTIL_SETTLED`: close is refused while the registered irreversible or
  non-detachable section remains active.

Window close, Escape, unmount, and navigation never manufacture approval,
rejection, cancellation completion, success, abandonment, or failure.
Apply/reject call the public response service for the exact pending interaction
and separately held secure bearer; Cancel calls the public cancellation
service; close uses the public detach service where permitted. A pending
interaction survives detachment, but observation cannot recreate response
authority. `INPUT` or `CHOICE` renders a typed unsupported disposition without
hiding lifecycle or settlement. Even when execution uses a contained
subprocess, the supervisor owns its handle, heartbeat, termination, reaping,
and reconciliation. TUI application shutdown uses supervisor shutdown policy
rather than modal teardown.

### D8 - Structural and behavioral conformance

Add a fixed-point operation-exposure census joining operation definitions, TUI
actions, CLI and MCP projections, executor factories, direct mutation/outbound
sites, and declared exclusions. Every operation exposure joins exactly one
operation definition and every exposure claim joins a real surface.
Opaque action callables, frontend-owned `asyncio.run`, direct outbound calls
from inbound projections, and unregistered worker-based mutations fail the
gate. Permanent allowlists and aggregate counts are insufficient.

The command-graph gate distinguishes callable availability from dedicated-migration
completion. It proves every `AVAILABLE` command joins a real full-screen interface,
every `NOT_IMPLEMENTED` request returns the typed refusal, explicit requests never
fall back to line mode, and introspection never launches a frontend. A separate
migration gate remains red while an authorized transitional CLI-to-inbound-TUI import
exists; capability tests cannot satisfy or waive that gate.

The accepted recovery-action census remains separate and authoritative for
`ActionReference`, verdict, command-leaf, result-schema, and MCP exposure joins.
Where a recovery action dispatches an operation, a third join validates exactly
one action-to-operation mapping. Neither census reimplements the other's scanner
or identity rules.

Registry-driven tests exercise each executor according to declared capability:
success, refusal, failure, exact-once settlement, effect reporting, stale or
mismatched interaction, deadline behavior, cancellation at declared safe
points, frontend detachment, cleanup failure, and restart reconciliation.
Projection tests prove TUI, CLI, and MCP render authoritative state without
becoming lifecycle owners.

Public-operation conformance additionally proves strict schema round trips and
endpoint-specific version refusal; fixed-point definition, schema, projector,
adapter, and production-composition parity; one-read observation atomicity
under an interleaved transition; independent lifecycle, terminal-condition,
and effect parity; progress fold and phase reset; bounded replay,
cursor-ahead refusal, expiry/compaction resynchronization, detach, and reconnect;
and absence of every persistence DTO from frontend imports and values.

REVIEW conformance resolves a registered safe projection from a fresh service
instance, covers every typed refusal and exact output-schema validation, and
proves resolution neither consumes nor grants response authority. Workspace-
refresh conformance resolves a registered typed target after process restart,
covers every typed refusal, and proves no caller-supplied result reference or
stale Workspace baseline is accepted.

Transient-financial conformance proves exact declaration/type/schema/baseline
binding, duplicate and concurrent submit/consume races, one executor
observation, every custody transition, expiry and cancellation, terminal and
shutdown cleanup, process-loss classification at every transition, domain
effect-receipt narrowing, Modelo compare-and-swap/effect-receipt co-commit, and
unique-sentinel non-retention. PRE_RELEASE persistence conformance proves exact
private-schema refusal, zero affected nonterminal invocations at breaking
cutover, and absence of superseded operation readers, migrators, fixtures, and
tests.

### D9 - Migration and grounded acceptance call sites

The opaque manager action execution seam and independent credential worker
lifecycle are retired as operation authorities. Existing visual components may
remain as projections during a tracked, shrinking migration census, but every
new operation must enter through the supervisor immediately.

Census synchronization is the mandatory end-to-end acceptance case because it
combines external authentication, device waiting, acquisition, typed review,
exact approval, stale-baseline detection, local mutation, progress, deadline,
cancellation, browser cleanup, and durable reconciliation. It must prove no
effect before approval, consumption of the reviewed operand, one operation ID
across all phases, authoritative cleanup before settlement, declared restart
behavior, and equivalent CLI/TUI semantics. Census field intent, merge policy,
phase, and persistence rules remain domain decisions and do not enter the
generic envelope.

Register census pull, review, and apply as one `RESUMABLE` operation with an
exact-baseline approval policy. It is cooperatively cancellable outside the
atomic profile-apply section, where `cancellable_now` becomes false. Acquisition
or `REJECT` settles with effect `NONE`; successful application settles
`UPDATED`; storage ambiguity settles honestly as `UNKNOWN`. One operation ID
must span Cl@ve external-device waiting, remote read, durable review, apply, and
resource settlement. The exact reviewed operand is applied through the existing
`apply_cotejo` authority; this ADR creates no second census writer.

The accepted census policies are reconciled as follows. Explicit review remains
mandatory because censo autofill reconciles AEAT observations with an
operator's declarations; the generic sync-control ruling for mirrors and
observation caches does not displace that consent boundary. The reviewed
observation, baseline revision and digest, field intents, and proposed-effect
digest form one encrypted, content-addressed operand. Approval binds the exact
operand and baseline. Apply delegates exclusively to `apply_cotejo` inside the
supervisor's irreversible section; no operation module may reproduce its merge
or write path. A stale baseline returns to review or refuses with effect `NONE`.
Resume consumes the persisted interaction checkpoint and secure operand and
must not repeat the remote read after review. These refinements are grounded in
`2026-08-24-tui-architecture-censo-operation-authority-reconciliation-research`.

Checkpoint publication is supervisor-owned. The executor context exposes a
typed secure-operand store for results produced after submission; publishing a
review interaction atomically persists that operand and journals only its
content digest. Consuming an apply or reject response durably records the
continuation intent and schedules the registered executor from the same
checkpoint. Startup reconciliation must recover both unconsumed review waits
and consumed-but-unsettled continuations from that durable state. Initial
execution may perform remote acquisition once; every review, response, and
restart continuation resolves the stored operand and is forbidden to reacquire.
The sole profile mutation remains the `apply_cotejo` compare-and-swap inside
the supervisor's irreversible section.

Register previous-filing history pull-all as one scoped `RECORDED` operation,
not initially resumable. The nested bulk-capture service already supports
`dry_run`, but the composed `pull_filed_history` operation does not expose it;
adding dry-run to the registered operation is therefore new API work and must
preserve identical discovery scope while producing effect `NONE`. A normal run
does not gain an unrelated generic approval ceremony merely because it writes.
Each captured observation is an atomic effect unit, so the outer effect may be
`NONE`, `UPDATED`, or `PARTIAL`. The completed `SyncRunRecord` remains domain
provenance referenced by the operation result, not the lifecycle journal.

Filing-history cancellation and aggregate timeout are initially
`UNSUPPORTED`. They may become cooperative only after the executor consumes the
supervisor cancellation scope, acknowledges between atomic units, records
checkpoints and actual committed effect, and proves cleanup before settlement.
Acceptance requires ordered discovery, pair, declaration, persistence, IVA
wallet, notification, and cleanup progress under one operation ID; typed
failure scope; effect equal to committed units; no dry-run provenance; and no
false cancelled or timed-out state while work continues.

Review requirements remain domain policy. Refused versus empty pairs and all
notices are always reviewable result projections. If recapture divergence or
wallet mutation later requires approval, the history executor must stage the
exact proposal before its governed write and use the same `REVIEW_READY`
apply/reject interaction. A post-write modal cannot retroactively supply
consent.

### D10 - Build-authoritative package topology

Closed, frontend-neutral operation axes live in
`src/cadrumo/core/operations.py`: lifecycle, terminal condition, effect,
durability, cancellation, deadline, close policy, event kind, and interaction
kind. This module contains value types only and imports no outer layer.

The operation platform lives at `src/cadrumo/application/operations/` with this
fixed ownership:

```text
cadrumo/application/operations/
  __init__.py          # sole public operation-platform facade
  _models.py           # private envelope, snapshot and receipt models
  _public.py           # strict public DTOs, version headers and refusals
  _observation.py      # atomic read port, fold and public observation service
  _financial_operand.py # distinct typed transient-financial custody protocol
  _projection_services.py # registered safe REVIEW and Workspace-refresh services
  _capabilities.py     # validated per-operation declarations
  _events.py           # ordered event and redacted log records
  _interactions.py     # request and response contracts
  _executor.py         # executor context and protocol
  _registry.py         # operation definitions and fixed-point catalogue
  _supervisor.py       # submit/start/observe/respond/cancel/settle/reconcile
  _secret_submission.py # runtime-only supervisor-owned one-shot secret broker port
  _journal.py          # journal and lock ports only
```

`__init__.py` is the only public import path for the operation contract set.
`_public.py` contains no persistence model or frontend type. `_observation.py`
may depend on the private journal port but returns only public DTOs.
`_financial_operand.py` is distinct from `_secret_submission.py`; sharing
low-level cleanup mechanics cannot merge their schemas, grants, checkpoints,
or reconciliation semantics. `_projection_services.py` invokes only registered
public protocols and imports no domain implementation. The registry fixed point
joins every exported schema, projector, adapter, and custody declaration to
production composition.

Initial operation executors remain with their application owners:
`src/cadrumo/application/user_profile/_censal_operation.py` and
`src/cadrumo/application/live/_filed_history_operation.py`. Their definitions
are exported only through the owning package facades.

The operation platform reuses `JournalRepositoryBase` as the hardened,
credential-free atomic file substrate rather than declaring a second generic
journal implementation. Existing reset and bundle-export journals remain their
domain authorities and are adapted through operation definitions only when they
need generic supervision; they are not migrated into a replacement record.
Generic lifecycle rows contain identifiers, revisions, safe state, digests, and
secure references only. Sensitive census proposals and other confidential
operands remain in their existing encrypted domain storage and are referenced by
digest. The owner-lease and transition adapter lives under
`src/cadrumo/adapters/persistence/operations/`; it composes the existing atomic
substrate and storage locks but does not redefine their security guarantees.

Entrypoints own concrete construction. `cadrumo.entrypoints.tui.launcher`
composes public application operation APIs with concrete persistence and
resource adapters for the TUI. CLI and MCP compose the same frontend-neutral
application services within their own entrypoint roots and do not import the
TUI. Composition introduces no new top-level package and contains no operation
policy.

The canonical production TUI root is `src/cadrumo/entrypoints/tui/`. All
Textual imports, widgets, screens, presentation models, frontend controllers,
frontend selection, terminal themes, TUI tests, and TUI development harnesses
live below this root.

```text
cadrumo/entrypoints/tui/
  __init__.py          # INTERFACE: narrow public facade only
  __main__.py          # INTERFACE: delegates only to launcher.main
  launcher.py          # INTERFACE: TUI composition root; consumes backend
  app.py               # JOIN: navigation and area composition only
  components/          # INTERFACE: TUI-local visual mechanics only
    __init__.py
    theme.py
    widgets.py
    forms.py
    dialogs.py
    status.py
    errors.py
    logs.py
  operations/
    __init__.py        # OPERATIONS: narrow operation-projection facade
    controller.py      # OPERATIONS: supervisor API calls only
    modal.py           # OPERATIONS: generic OperationModal
    projection.py      # OPERATIONS: envelope to immutable TUI view model
    interactions.py    # OPERATIONS: typed renderers, never domain policy
    logs.py             # OPERATIONS: cursor/subscription projection
  profile/             # INTERFACE: profile task projections
    __init__.py
    app.py
    overview.py
    editor.py
    status.py
    sync_review.py
  secret/              # INTERFACE: ephemeral secret-entry projections
    __init__.py
    credentials.py
    login.py
    registration.py
    passphrase.py
  flows/               # INTERFACE: renderer over application.flows only
    __init__.py
    app.py
    question.py
    review.py
    projection.py
    dialogs.py
  modelo/              # RESERVED: do not create until a Modelo campaign
    view/               # RESERVED future home; no importable module yet
    edit/               # RESERVED future home; no importable module yet
  devtools/             # INTERFACE: TUI-only pilot/replay/surface tooling
  tests/                # INTERFACE/OPERATIONS: follows module ownership
```

`INTERFACE` rows belong to the `tui-interface` concern, `OPERATIONS` rows to
this concern, and `JOIN` rows to an explicit integration step after both lanes
are complete. `RESERVED` rows establish ownership only: they MUST NOT be created
as empty importable packages or used until a future Modelo ADR defines real
contracts and tests.

`components` contains reusable TUI presentation mechanics only. It owns no
application lifecycle, domain policy, persistence, outbound access, wizard
state, or frontend composition. `forms.py` owns
immutable visual form contracts and widgets, not validation or orchestration;
`logs.py` owns bounded log rendering, not subscription or retention; and
`errors.py` renders already-safe canonical error envelopes without accepting raw
exceptions or reclassifying failures.

Packaging adds a dedicated console entry point targeting
`cadrumo.entrypoints.tui.launcher:main` directly. CLI modules do not import the
TUI to start it. The existing automatic CLI-to-TUI import path is retired rather
than kept as a shim.

The human CLI exposes `aeat --tui [COMMAND_PATH]` as one root-owned routing request.
While the dedicated launcher remains incomplete, an `AVAILABLE` command may invoke its
existing callable full-screen interface through the bounded legacy CLI-to-inbound-TUI
seam. A genuinely unimplemented command refuses with `TUI_NOT_IMPLEMENTED`; explicit
`--tui` never falls back to line mode. Introspection takes precedence.

This temporary authorization is not the target topology. Packaging must still add the
dedicated launcher, migrate every enrolled route and reverse consumer, remove CLI
imports of TUI implementation, and delete the legacy inbound TUI without a compatibility
facade. Current capability metadata cannot mark any of those steps complete.

That retirement cannot land ahead of a replacement for the accepted frontend
selection contract. Existing commands preserve line-mode fallback and
capability negotiation through frontend-neutral application contracts; a
full-screen TUI starts through its installed entrypoint rather than a CLI import.
The affected composition clauses in `2026-07-23-tui-wizard-substrate-adr` and
`2026-07-24-profile-bundle-tui-adr` must be amended without changing their
application-owned flow semantics.

### D11 - Strict dependency direction

`cadrumo.entrypoints.tui` is an outermost entrypoint package. No backend
package, CLI or MCP entrypoint, shared test utility, or development tool may
import, load, re-export, annotate against, or register from it. Packaging
metadata and out-of-process smoke execution are the only external references.
TUI-specific tests live in `cadrumo.entrypoints.tui.tests`; pilot, replay,
screenshot, and surface tools live in `cadrumo.entrypoints.tui.devtools`.

No Textual class, widget, screen, CSS/theme rule, TUI form or dialog, TUI view
model, terminal interaction controller, TUI frontend-selection function, or TUI
test utility may live outside `src/cadrumo/entrypoints/tui/`. Backend packages retain only
frontend-neutral application/domain contracts that CLI, MCP, TUI, and future
interfaces may consume independently. A model is not made backend-neutral by
renaming it if its fields encode screen, widget, modal, spinner, keyboard,
terminal-layout, or localized presentation concerns.

Inside the boundary:

- `cadrumo.entrypoints.tui.launcher` is the concrete TUI composition root and
  the only TUI module allowed to wire concrete adapters.
- `app.py`, `operations`, `profile`, `secret`, and `flows` consume injected
  dependencies plus public application and core facades. They MUST NOT import
  concrete adapters, repositories, private application modules, CLI or MCP, or
  domain internals.
- `cadrumo.application.operations` MUST NOT import Textual, a frontend or
  entrypoint or concrete adapter.
- Adapter implementations never import entrypoints.
- `components` may depend on Textual and layer-neutral core presentation
  primitives, but not on TUI feature packages, `app`, or `launcher`.
- `operations`, `profile`, `secret`, and `flows` may share only `components`;
  they do not import one another. `app.py` is their TUI composition point.
- Cross-package callers use `cadrumo.application.operations` and owning
  application package facades. Deep private imports are forbidden.
- `cadrumo.entrypoints.tui.__init__` exports only launcher-level public API.

Import-linter enforces both directions, the launcher-only concrete-wiring
exception, component independence, and adapter-to-entrypoint prohibition. An
AST gate also rejects dynamic strings, `TYPE_CHECKING`, re-export, annotation,
registration, and plugin-discovery bypasses; Textual imports outside the TUI
entrypoint; TUI-named presentation types outside its root; and private-facade
reaches.

### D12 - Separate migration lanes before wizard restructuring

The operation-platform lane owns `cadrumo.core.operations`,
`cadrumo.application.operations`, the persistence operation adapter,
application-owned executors, `cadrumo.entrypoints.tui.operations`, and
`OperationModal`.

The `tui-interface` lane owns `entrypoints.tui.components`, `profile`, `secret`,
`flows`, `devtools`, and presentation-owned tests. It MUST NOT edit operation
lifecycle, supervisor, journal, executor, or application flow semantics. The
operation lane MUST NOT edit navigation, visual design, wizard semantics, or
secret-entry presentation.

The integration lane owns `entrypoints.tui.__init__`, `__main__`, `launcher`,
`app`, packaging metadata, and root navigation. It lands only after the two
foundational lanes are green. `components` is the only shared TUI-local
presentation seam; the operation lane consumes its facade but places no
lifecycle or policy there.

The current reverse imports form a generated migration manifest keyed by exact
module, imported symbol, and consumer class. It includes every production
entrypoint, the full legacy facade export set, application parity test, TUI-owned
tests, manager pilot, and `dev/tui` surface - not only the currently named manager
and wizard examples. Each row records its owning lane, replacement public
facade or out-of-process boundary, and deletion proof. The manifest is generated
from AST discovery and checked against `rg`; prose counts and allowlists are not
authoritative. No new identity may enter it.

Completion requires no TUI or Textual code outside `entrypoints.tui`, no outside
Python imports of that package, an empty legacy inventory, exact joins among
operation definitions, entrypoint composition, and TUI/CLI/MCP projections,
the separate accepted recovery-action census remaining green, and deletion of
`cadrumo.adapters.inbound.tui` without a compatibility facade.

### D13 - One authorizing plan and no parallel implementation plans

Implementation is governed by one canonical `tui-architecture` roll-up plan.
Related frontend work may have its own information-architecture plan, but it
MUST NOT duplicate this plan's operation platform or package migration.

Before S39 registers profile login, the roll-up plan must add and close the
generic `EphemeralSecretSubmission` prerequisite: credential-free request
storage, the supervisor-owned one-shot broker, restart and cleanup semantics,
and real non-retention conformance. S39 then composes that public capability and
the existing profile-login authority exactly once; it must not introduce a
per-login callback, persistence exception, or shadow authentication path.

Before any visual operation projection begins, the roll-up plan must produce
the exact C0 artifact
`.vault/reference/2026-08-24-tui-operation-observation-dependency-receipt.md`.
It validates as `TuiOperationObservationDependencyReceiptV1` under the sole
live-tree validator
`src/cadrumo/application/operations/tests/test_public_operation_dependency_receipt.py`.
No alternate path, schema alias, prose attestation, fixture-only validator, or
receipt artifact not committed at the validator's clean current HEAD opens C0.

Every dependency receipt uses one non-self-referential two-commit contract. Its
current-only `implementation_commit` is clean commit A, the commit from which
all covered implementation evidence is captured. S124 writes that receipt and
commits the artifact as B. The sole validator runs only at clean current HEAD B;
it requires A to be an ancestor of B, recomputes the covered source-tree digest
at B and requires equality with the receipt, and requires the bytes being
parsed to equal `git show B:<receipt path>`. B is derived from the validator
context and is never a receipt field: storing it in the artifact would recreate
a commit-hash self-reference. The covered source digest intentionally excludes
the vault artifact; committed-byte equality is the separate artifact-attestation
proof. No staged-file exclusion, alias, shim, fallback parser, or alternate
attestation path is permitted.

The C0 receipt is captured from clean implementation commit A and records:

- receipt schema version, `implementation_commit`, covered source-tree digest,
  and the clean-current-HEAD B attestation requirements above;
- this governing stem, its `accepted` status, post-amendment body hash and
  producing commit, plus ancestry to the receipt;
- staging stem `2026-08-24-tui-operation-observation-adr`, its required
  `rejected` status and body hash, proving it is provenance rather than a second
  authority;
- public-definition manifest, observation, REVIEW-resolver, and Workspace-
  refresh endpoint versions; every registered schema identity and fingerprint;
  every definition digest; and exact `contract_set_digest`;
- sorted public export and observation/review/cancel/detach/respond/refresh
  capability inventories and digests, plus production-composition parity;
- real-adapter atomic observation under interleaved transition, independent
  lifecycle/terminal/effect parity, progress folding and phase reset, bounded
  replay, cursor-ahead refusal, expiry/compaction resynchronization, detach, and
  reconnect;
- complete public-state parity for action reference, definition, request,
  result, REVIEW, response, and refresh schema identities and digests;
- atomic invocation definition-digest pinning plus acquisition, observation,
  response, and reconciliation refusal after simulated registry drift;
- registered safe REVIEW resolution from a fresh service instance, every typed
  refusal, strict output validation, and proof that resolution neither consumes
  nor grants response authority;
- registered typed Workspace-refresh resolution after process restart, every
  typed refusal, and proof that no caller-supplied result reference or stale
  Workspace baseline is accepted;
- exact current-version round trips and endpoint-specific unsupported-version,
  schema-mismatch, and definition-digest refusals;
- PRE_RELEASE exact private-schema refusal, zero affected nonterminal
  invocations at breaking cutover, and deletion of superseded operation
  readers, migrators, fixtures, and tests; and
- forbidden-import and sentinel non-retention proof across public DTOs,
  journal, events, receipts, diagnostics, traces, logs, exceptions, and
  persistence materializations.

This receipt opens only the C0 operation-platform public-projection cohort. It
does not claim transient financial custody exists and cannot open C1 read-only
Modelo relocation, C2 Workspace, C3 edit, C4 action enrollment, or C5 closure.

The operation-side prerequisite for C3 is the separate exact artifact
`.vault/reference/2026-08-24-tui-operation-financial-operand-dependency-receipt.md`.
It validates as `TuiOperationFinancialOperandDependencyReceiptV1` under the
sole live-tree validator
`src/cadrumo/application/operations/tests/test_financial_operand_dependency_receipt.py`.
It is not produced during C0 and cannot be replaced by generic
`EphemeralSecretSubmission` conformance.

The financial receipt's closed predecessor tuple contains the exact C0 receipt
path and schema plus its `implementation_commit`, covered source digest, and
committed artifact digest as separate facts; this accepted parent's then-current
body hash; accepted stem `2026-08-24-modelo-edit-contract-adr` and its body
hash; exact Workspace predecessor
`.vault/reference/2026-08-24-tui-registry-api-gate-c2-dependency-receipt.md` as
`ModeloWorkspaceC2DependencyReceiptV1` with its `implementation_commit`, covered
source digest, and committed artifact digest as separate facts; and the clean
implementation commit under validation. The same A/B contract applies to C0,
Workspace C2, financial C3, Edit C3, and every downstream receipt: each
predecessor artifact is validated at its own clean committed target before its
three provenance facts are consumed. It records and proves:

- protocol version `1`, every enrolled declaration and operand schema identity,
  affected operation-definition digests, and production registry/DI parity;
- exact type, operation, definition, revision, random-grant fingerprint,
  baseline, expiry, and schema binding without content hashing;
- atomic `awaiting_submission -> bound -> delivery_started ->
  delivery_acknowledged -> released` transitions, duplicate and concurrent
  submit/consume races, and exactly one executor observation;
- expiry, pre-delivery cancellation, terminal settlement, owner cleanup, and
  supervisor-shutdown release;
- crash injection before binding, while bound, after delivery start, after
  acknowledgement, after release, and across terminal settlement, with exact
  `NONE`/`UNKNOWN` classification and domain effect-receipt narrowing;
- an enrolled Modelo writer's atomic `ModeloEditBaselineV1` compare-and-swap,
  idempotent effect-receipt co-commit, stale-baseline refusal, and proof that a
  refreshed read never masquerades as effect evidence; and
- unique-sentinel absence from every forbidden operation, frontend,
  filesystem, diagnostic, log, trace, exception, receipt, digest, and cache
  surface, allowing only the successful canonical encrypted Modelo value.

Passing this receipt opens only the operation-custody half of C3. C3 still
requires the accepted Modelo editor decision, applicable Workspace and
interface predecessor receipts, and their live validators. Neither operation
receipt opens C4 or C5.

Within the one canonical plan, `W05.P11.S60` consumes the public observation
service rather than supervisor inspection or persistence DTOs; `S61` projects
only `OperationPublicProjectionV1`; `S62` consumes
`OperationPublicEventPageV1`; and `S63` is restricted to registered safe REVIEW
projection plus separately authorized `APPLY`/`REJECT`. The public-definition
manifest and Workspace-refresh service precede C0. The transient-financial-
operand protocol is scheduled only at the future C3 dependency step. No
separate operation, editor, receipt-migration, or implementation plan is
authorized.

The roll-up plan schedules foundations upward: structural census and dependency
gates; core operation axes and application contracts; registry, supervisor,
journal ports, and persistence adapter; real executor lifecycle proofs; TUI
components and mechanical presentation relocation; TUI operation projections;
census and filing-history integration; launcher/app/packaging composition;
reverse-consumer migration and legacy deletion; then real-behavior lifecycle,
installed-entrypoint, and terminal-size verification. Every step names its
owned modules and deletion proof. A step cannot close while a legacy import,
Textual module, TUI test helper, or development surface remains outside
`entrypoints.tui`.

## Rationale

The chosen design is the only option that places execution truth with the layer
that observes validated intent, policy, interaction, resources, effects, and
cleanup. Presentation DTOs and shared events cannot make cancellation or
settlement authoritative, while reusing the CLI wire envelope would invert the
established projection boundary (`2026-08-11-tui-architecture-research`).

Three independent axes prevent a terminal label from hiding committed or
uncertain effects. Capability declarations prevent the interface from promising
cancellation, deadlines, or resumability that an executor cannot provide.
Exact interaction binding closes the gap between what an operator reviewed and
what the application performs. The distinct operation registry joins existing
recovery actions only where dispatch actually connects them, preserving the
accepted action catalogue's narrower authority
(`2026-08-09-cli-action-envelope-hardening-adr`).

The public observation materialization is the only option that gives every
frontend an internally consistent lifecycle/event/progress view without
publishing journal topology or duplicating the authoritative fold. Registered
safe REVIEW and Workspace-refresh projectors keep domain interpretation with
the owning application while the generic operation package retains schema,
version, and refusal authority. Distinct transient-financial custody preserves
single-use application-memory handoff and honest crash classification without
turning an editor draft into a resumable operation operand. These refinements
are grounded in `2026-08-24-tui-operation-observation-research`.

## Consequences

- Every current and future frontend-triggered operation gains one authoritative
  identity, lifecycle, interaction protocol, deadline source, cleanup boundary,
  and terminal receipt.
- TUI progress, spinner, controls, cancellation, and restart/resume become
  projections of application state rather than Textual worker mechanics.
- Long-running asynchronous work exposes replayable live feedback and redacted
  logs under one operation identity, including detach and reconnect.
- Reviewable results enter one typed apply/reject continuation, allowing future
  operations to separate computation from effect without inventing a modal or
  callback contract.
- CLI and MCP retain established wire contracts while sharing execution
  semantics with the TUI.
- Approval becomes auditable and exact; a frontend gesture cannot authorize
  changed input or a changed baseline.
- Cancellation claims become honest, and operations that cannot stop safely
  expose that limitation instead of a false control.
- The fixed-point gates make bypasses mechanically detectable and bind future
  tool implementations to the architecture.
- Migration is broad: manager actions, credential attempts, progress callbacks,
  and direct frontend orchestration must move behind registered executors.
- Durable supervision adds credential-free lifecycle journal volume, leases,
  reconciliation, revision, and retention obligations. Sensitive operands remain
  in encrypted domain storage and are referenced by digest.
- The effect axis exposes partial and uncertain outcomes but requires executors
  to report post-commit failures honestly.
- Census becomes a demanding proof of the platform contract without turning
  the general architecture into census-specific machinery.
- Frontends gain one strict current-only operation definition, observation,
  event-page, safe REVIEW, and typed Workspace-refresh contract without
  receiving persistence records or secure-reference topology.
- Progress, replay, detach, reconnect, and resynchronization share one atomic
  anchor; terminal condition remains independent from lifecycle, effect,
  result, and refusal.
- Safe REVIEW content remains resolvable after restart, but observation never
  grants apply/reject authority.
- Successful terminal operations may yield a typed Workspace refresh target;
  Workspace still owns the new authoritative read and baseline.
- Financial edit values may cross one single-consumer application-memory
  handoff, but never become a resumable operand. Crash after delivery start is
  `UNKNOWN` unless an authoritative domain receipt narrows it.
- Public version changes and private journal changes remain separate. While
  `PRE_RELEASE`, both use current-only cutover and no private-schema migration
  path survives.
- C0 and C3 remain independently gated by their exact dependency receipts;
  neither receipt authorizes a later Modelo or visual cohort by implication.
